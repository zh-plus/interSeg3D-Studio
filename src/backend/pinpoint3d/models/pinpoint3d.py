# ------------------------------------------------------------------------
# 
# 
# ------------------------------------------------------------------------
from tkinter import N
import torch
from torch import Tensor
import torch.nn as nn
import MinkowskiEngine.MinkowskiOps as me
from MinkowskiEngine.MinkowskiPooling import MinkowskiAvgPooling
import numpy as np
from torch.nn import functional as F
from .modules.common import conv
from .modules.attention_block import *
from .position_embedding import PositionEmbeddingCoordsSine, PositionalEncoding3D, PositionalEncoding1D
from torch.cuda.amp import autocast
from .backbone import build_backbone
import MinkowskiEngine as ME

import itertools

def mink_conv(in_channels, out_channels, kernel_size, stride=1, bias=True, D=3):
    return ME.MinkowskiConvolution(
        in_channels, out_channels, kernel_size=kernel_size,
        stride=stride, dimension=D, bias=bias
    )

def _safe_replace_feature(x: ME.SparseTensor, new_F):
    if hasattr(x, "replace_feature"):
        return x.replace_feature(new_F)
    return ME.SparseTensor(
        features=new_F,
        coordinate_map_key=x.coordinate_map_key,
        coordinate_manager=x.coordinate_manager
    )

class Adapter1x1(nn.Module):
    def __init__(self, dim, bottleneck_ratio=1.0, use_bn=True,
                 residual_scale=0.3, init_last='kaiming', D=3):
        super().__init__()
        hidden = max(1, int(dim * bottleneck_ratio))

        layers = [mink_conv(dim, hidden, kernel_size=1, D=D)]
        if use_bn:
            layers.append(ME.MinkowskiBatchNorm(hidden))
        layers.append(ME.MinkowskiReLU(inplace=True))
        layers.append(mink_conv(hidden, dim, kernel_size=1, D=D))
        self.net = nn.Sequential(*layers)
        self.res_scale = residual_scale

        if init_last == 'kaiming':
            for m in self.net.modules():
                if isinstance(m, ME.MinkowskiConvolution) and m.in_channels == hidden and m.out_channels == dim:
                    nn.init.kaiming_uniform_(m.kernel, a=1.0)
        else:
            for m in self.net.modules():
                if isinstance(m, ME.MinkowskiConvolution) and m.in_channels == hidden and m.out_channels == dim:
                    nn.init.zeros_(m.kernel)

    def forward(self, x: ME.SparseTensor) -> ME.SparseTensor:
        delta = self.net(x)
        new_F = x.F + self.res_scale * delta.F
        return _safe_replace_feature(x, new_F)


class PinPoint3D(nn.Module):
    def __init__(self, backbone, hidden_dim, num_heads, dim_feedforward,
                 shared_decoder, num_decoders, num_bg_queries, dropout, pre_norm,
                 positional_encoding_type, normalize_pos_enc, hlevels,
                 voxel_size, gauss_scale, aux, use_adapter=True, 
                 adapter_bottleneck_ratio=1, adapter_use_bn=True, adapter_res_scale=0.1
                 ):
        super().__init__()

        self.gauss_scale = gauss_scale
        self.voxel_size = voxel_size
        self.hlevels = hlevels
        self.normalize_pos_enc = normalize_pos_enc
        self.num_decoders = num_decoders
        self.num_bg_queries = num_bg_queries
        self.dropout = dropout
        self.pre_norm = pre_norm
        self.shared_decoder = shared_decoder
        self.mask_dim = hidden_dim
        self.num_heads = num_heads
        self.pos_enc_type = positional_encoding_type
        self.aux = aux

        self.backbone = backbone

        self.use_adapter = use_adapter
        if self.use_adapter:
            self.adapter = Adapter1x1(
                dim=self.mask_dim,
                bottleneck_ratio=adapter_bottleneck_ratio,
                use_bn=adapter_use_bn,
                residual_scale=adapter_res_scale,
                D=3
            )
        else:
            self.adapter = None
        
            
        self.lin_squeeze_head = conv(
            self.backbone.PLANES[7], self.mask_dim, kernel_size=1, stride=1, bias=True, D=3
        )

        self.bg_query_feat = nn.Embedding(num_bg_queries, hidden_dim)
        self.bg_query_pos = nn.Embedding(num_bg_queries, hidden_dim)


        self.mask_embed_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim)
        )

        self.part_mask_embed_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim)
        )


        if self.pos_enc_type == "legacy":
            self.pos_enc = PositionalEncoding3D(channels=self.mask_dim)
        elif self.pos_enc_type == "fourier":
            self.pos_enc = PositionEmbeddingCoordsSine(pos_type="fourier",
                                                       d_pos=self.mask_dim,
                                                       gauss_scale=self.gauss_scale,
                                                       normalize=self.normalize_pos_enc)
        elif self.pos_enc_type == "sine":
            self.pos_enc = PositionEmbeddingCoordsSine(pos_type="sine",
                                                       d_pos=self.mask_dim,
                                                       normalize=self.normalize_pos_enc)
        else:
            assert False, 'pos enc type not known'

        self.pooling = MinkowskiAvgPooling(kernel_size=2, stride=2, dimension=3)

        self.masked_transformer_decoder = nn.ModuleList()

        # Click-to-scene attention
        self.c2s_attention = nn.ModuleList()

        # Click-to-click attention
        self.c2c_attention = nn.ModuleList()

        # FFN
        self.ffn_attention = nn.ModuleList()

        # Scene-to-click attention
        self.s2c_attention = nn.ModuleList()

        # Parts-to-object attention
        self.p_c2o_attention = nn.ModuleList()

        # Click-to-click attention
        self.p_c2c_attention = nn.ModuleList()
        
        # Parts-to-parts attention  
        self.p_ffn_attention = nn.ModuleList()

        # Part FFN
        self.p_o2c_attention = nn.ModuleList()


        num_shared = self.num_decoders if not self.shared_decoder else 1

        for _ in range(num_shared):
            tmp_c2s_attention = nn.ModuleList()
            tmp_s2c_attention = nn.ModuleList()
            tmp_c2c_attention = nn.ModuleList()
            tmp_ffn_attention = nn.ModuleList()

            tmp_p_c2o_attention = nn.ModuleList()
            tmp_p_c2c_attention = nn.ModuleList()
            tmp_p_ffn_attention = nn.ModuleList()
            tmp_p_o2c_attention = nn.ModuleList()


            for i, hlevel in enumerate(self.hlevels):
                tmp_c2s_attention.append(
                    CrossAttentionLayer(
                        d_model=self.mask_dim,
                        nhead=self.num_heads,
                        dropout=self.dropout,
                        normalize_before=self.pre_norm
                    )
                )

                tmp_s2c_attention.append(
                    CrossAttentionLayer(
                        d_model=self.mask_dim,
                        nhead=self.num_heads,
                        dropout=self.dropout,
                        normalize_before=self.pre_norm
                    )
                )

                tmp_c2c_attention.append(
                    SelfAttentionLayer(
                        d_model=self.mask_dim,
                        nhead=self.num_heads,
                        dropout=self.dropout,
                        normalize_before=self.pre_norm
                    )
                )

                tmp_ffn_attention.append(
                    FFNLayer(
                        d_model=self.mask_dim,
                        dim_feedforward=dim_feedforward,
                        dropout=self.dropout,
                        normalize_before=self.pre_norm
                    )
                )

                tmp_p_c2o_attention.append(
                    CrossAttentionLayer(
                        d_model=self.mask_dim,
                        nhead=self.num_heads,
                        dropout=self.dropout,
                        normalize_before=self.pre_norm
                    )
                )

                tmp_p_c2c_attention.append(
                    SelfAttentionLayer(
                        d_model=self.mask_dim,
                        nhead=self.num_heads,
                        dropout=self.dropout,
                        normalize_before=self.pre_norm
                    )
                )

                tmp_p_ffn_attention.append(
                    FFNLayer(
                        d_model=self.mask_dim,
                        dim_feedforward=dim_feedforward,
                        dropout=self.dropout,
                        normalize_before=self.pre_norm
                    )
                )
                
                tmp_p_o2c_attention.append(
                    CrossAttentionLayer(
                        d_model=self.mask_dim,
                        nhead=self.num_heads,
                        dropout=self.dropout,
                        normalize_before=self.pre_norm
                    )
                )


            self.c2s_attention.append(tmp_c2s_attention)
            self.s2c_attention.append(tmp_s2c_attention)
            self.c2c_attention.append(tmp_c2c_attention)
            self.ffn_attention.append(tmp_ffn_attention)
            self.p_c2o_attention.append(tmp_p_c2o_attention)
            self.p_c2c_attention.append(tmp_p_c2c_attention) 
            self.p_ffn_attention.append(tmp_p_ffn_attention)
            self.p_o2c_attention.append(tmp_p_o2c_attention)

        self.decoder_norm = nn.LayerNorm(hidden_dim)
        self.decoder_norm_part = nn.LayerNorm(hidden_dim)
        self.time_encode = PositionalEncoding1D(hidden_dim, 200)


    def get_pos_encs(self, coords):
        pos_encodings_pcd = []

        for i in range(len(coords)):
            pos_encodings_pcd.append([[]])
            ### this is a trick to bypass a bug in Minkowski Engine cpu version
            if coords[i].F.is_cuda:
                coords_batches = coords[i].decomposed_features
            else:
                coords_batches = [coords[i].F]
            for coords_batch in coords_batches:
                scene_min = coords_batch.min(dim=0)[0][None, ...]
                scene_max = coords_batch.max(dim=0)[0][None, ...]

                with autocast(enabled=False):
                    tmp = self.pos_enc(coords_batch[None, ...].float(),
                                       input_range=[scene_min, scene_max])

                pos_encodings_pcd[-1][0].append(tmp.squeeze(0).permute((1, 0)))

        return pos_encodings_pcd

    def forward_backbone(self, x, raw_coordinates=None):
        pcd_features, aux = self.backbone(x)

        with torch.no_grad():
            coordinates = me.SparseTensor(features=raw_coordinates,
                                          coordinate_manager=aux[-1].coordinate_manager,
                                          coordinate_map_key=aux[-1].coordinate_map_key,
                                          device=aux[-1].device)
            coords = [coordinates]
            for _ in reversed(range(len(aux)-1)):
                coords.append(self.pooling(coords[-1]))

            coords.reverse()

        pos_encodings_pcd = self.get_pos_encs(coords)

        pcd_features = self.lin_squeeze_head(pcd_features)
        if self.adapter is not None:
            pcd_features = self.adapter(pcd_features)

        return pcd_features, aux, coordinates, pos_encodings_pcd
    
    def freeze_module(self, m):
        for p in m.parameters():
            p.requires_grad = False

    def freeze_object_decoder(self):
        self.freeze_module(self.c2s_attention)
        self.freeze_module(self.c2c_attention)
        self.freeze_module(self.ffn_attention)
        self.freeze_module(self.s2c_attention)
        self.freeze_module(self.backbone)
        self.freeze_module(self.mask_embed_head)
        self.freeze_module(self.lin_squeeze_head)
        self.freeze_module(self.decoder_norm)

    def generate_object_features(self, src_pcd, pred_label: Tensor):
        object_features = torch.zeros_like(src_pcd)
        N_query = pred_label.max().item() + 1

        for query_idx in range(N_query):
            mask = (pred_label == query_idx)
            if mask.any():
                object_features[mask] = src_pcd[mask]

        return object_features
    
    def nest_foreground_clicks(self, click_dict: dict) -> dict:
        """
        将多层点击结构合并为统一格式：
        例如：
        {'0': [], '1': {'1':[3961],'2':[3385]}, '2':{'1':[3984],'2':[1376]}}
        → {'0': [], '1': {'1':[3961],'2':[3385],'3':[3984],'4':[1376]}}
        """
        new_dict = {'0': click_dict.get('0', [])}
        merged = {}
        sub_index = 1

        for k, v in click_dict.items():
            if k == '0':
                continue
            # 如果该层是字典，则合并所有子项
            if isinstance(v, dict):
                for subk, subv in v.items():
                    merged[str(sub_index)] = subv
                    sub_index += 1
            else:
                # 如果该层是直接列表，也加进去
                merged[str(sub_index)] = v
                sub_index += 1

        new_dict['1'] = merged
        return new_dict


    def forward_mask(self, pcd_features, aux, coordinates, pos_encodings_pcd, click_idx=None, click_time_idx=None, target_object_id=None):

        batch_size = pcd_features.C[:,0].max() + 1

        object_predictions_mask = [[] for i in range(batch_size)]
        part_predictions_mask = [[] for i in range(batch_size)]

        bg_learn_queries = self.bg_query_feat.weight.unsqueeze(0).repeat(batch_size, 1, 1)
        bg_learn_query_pos = self.bg_query_pos.weight.unsqueeze(0).repeat(batch_size, 1, 1)


        for b in range(batch_size):

            if coordinates.F.is_cuda:
                mins = coordinates.decomposed_features[b].min(dim=0)[0].unsqueeze(0)
                maxs = coordinates.decomposed_features[b].max(dim=0)[0].unsqueeze(0)
            else:
                mins = coordinates.F.min(dim=0)[0].unsqueeze(0)
                maxs = coordinates.F.max(dim=0)[0].unsqueeze(0)

            # click_idx_sample = click_idx[b]
            # click_time_idx_sample = click_time_idx[b]
            print(click_idx[b])
            print(click_time_idx[b])

            click_idx_sample = self.nest_foreground_clicks(click_idx[b])
            click_time_idx_sample = self.nest_foreground_clicks(click_time_idx[b])

            print(click_idx_sample)
            print(click_time_idx_sample)

            # address trouble case
            part_fg_query_num_split = []
            for obj_key, part_dict in click_idx_sample.items():
                if obj_key == '0':
                    continue
                if obj_key != str(target_object_id[b]):
                    continue
                for part_id, click_indices in part_dict.items():
                    if part_id == '0':
                        continue
                    part_fg_query_num_split.append(len(click_indices))
                    if len(click_indices) == 0:
                        return "ignore this test"
            # address trouble case

            bg_click_idx = click_idx_sample['0']

            fg_click_coords_list = []
            fg_query_num_split = []
            fg_object_query_num_split = []
            fg_clicks_time_idx = []

            for obj_id in click_idx_sample:
                if obj_id == '0':
                    continue
                object_split = 0

                for part_id in click_idx_sample[obj_id]:
                    click_indices = click_idx_sample[obj_id][part_id]
                    time_indices = click_time_idx_sample[obj_id][part_id]

                    if len(click_indices) == 0:
                        continue

                    if coordinates.F.is_cuda:
                        coords = coordinates.decomposed_features[b][click_indices]
                    else:
                        coords = coordinates.F[click_indices]

                    fg_click_coords_list.append(coords)
                    fg_clicks_time_idx.extend(time_indices)
                    fg_query_num_split.append(len(click_indices))
                    object_split += len(click_indices)
                fg_object_query_num_split.append(object_split)

            fg_query_num = sum(fg_query_num_split)
            fg_clicks_coords = torch.vstack(fg_click_coords_list).unsqueeze(0)
            

            fg_query_pos = self.pos_enc(fg_clicks_coords.float(),
                                    input_range=[mins, maxs]
                                    )
            fg_query_time = self.time_encode[fg_clicks_time_idx].T.unsqueeze(0).to(fg_query_pos.device)

            fg_query_pos = fg_query_pos + fg_query_time

            if len(bg_click_idx)!=0:
                if coordinates.F.is_cuda:
                    bg_click_coords = coordinates.decomposed_features[b][bg_click_idx].unsqueeze(0)
                else:
                    bg_click_coords = coordinates.F[bg_click_idx].unsqueeze(0)
                bg_query_pos = self.pos_enc(bg_click_coords.float(),
                                        input_range=[mins, maxs]
                                        )
                bg_query_time = self.time_encode[click_time_idx_sample['0']].T.unsqueeze(0).to(bg_query_pos.device)
                bg_query_pos = bg_query_pos + bg_query_time

                bg_query_pos = torch.cat([bg_learn_query_pos[b].T.unsqueeze(0), bg_query_pos],dim=-1)
            else:
                bg_query_pos = bg_learn_query_pos[b].T.unsqueeze(0)

            fg_query_pos = fg_query_pos.permute((2, 0, 1))[:,0,:]     
            bg_query_pos = bg_query_pos.permute((2, 0, 1))[:,0,:]

            bg_query_num = bg_query_pos.shape[0]

            fg_query_feat_list = []
            for obj_id in click_idx_sample:
                if obj_id == '0':
                    continue
                for part_id in click_idx_sample[obj_id]:
                    click_indices = click_idx_sample[obj_id][part_id]
                    if len(click_indices) == 0:
                        continue
                    if pcd_features.F.is_cuda:
                        feats = pcd_features.decomposed_features[b][click_indices]
                    else:
                        feats = pcd_features.F[click_indices]
                    fg_query_feat_list.append(feats)
            fg_queries = torch.vstack(fg_query_feat_list)

            fg_queries_per_object =torch.split(fg_queries, fg_object_query_num_split, dim=0)
            fg_query_pos_per_object = torch.split(fg_query_pos, fg_object_query_num_split, dim=0)

            if len(bg_click_idx)!=0:
                if pcd_features.F.is_cuda:
                    bg_queries = pcd_features.decomposed_features[b][bg_click_idx,:]
                else:
                    bg_queries = pcd_features.F[bg_click_idx,:]
                bg_queries = torch.cat([bg_learn_queries[b], bg_queries], dim=0)
            else:
                bg_queries = bg_learn_queries[b]

            if pcd_features.F.is_cuda:
                src_pcd = pcd_features.decomposed_features[b]
            else:
                src_pcd = pcd_features.F

            refine_time = 0

            for decoder_counter in range(self.num_decoders):
                if self.shared_decoder:
                    decoder_counter = 0
                for i, hlevel in enumerate(self.hlevels):

                    pos_enc = pos_encodings_pcd[hlevel][0][b]

                    if refine_time == 0:
                        attn_mask = None

                    output = self.c2s_attention[decoder_counter][i](
                        torch.cat([fg_queries, bg_queries],dim=0),
                        src_pcd,
                        memory_mask=attn_mask,
                        memory_key_padding_mask=None,
                        pos=pos_enc,
                        query_pos=torch.cat([fg_query_pos, bg_query_pos], dim=0)
                    )

                    output = self.c2c_attention[decoder_counter][i](
                        output,
                        tgt_mask=None,
                        tgt_key_padding_mask=None,
                        query_pos=torch.cat([fg_query_pos, bg_query_pos], dim=0)
                    )

                    queries = self.ffn_attention[decoder_counter][i](
                        output
                    )
                    
                    src_pcd = self.s2c_attention[decoder_counter][i](
                        src_pcd,
                        queries,
                        memory_mask=None,
                        memory_key_padding_mask=None,
                        pos=torch.cat([fg_query_pos, bg_query_pos], dim=0),
                        query_pos=pos_enc
                    )

                    fg_queries, bg_queries = queries.split([fg_query_num, bg_query_num], 0)

                    outputs_mask, attn_mask = self.mask_module(
                                                        fg_queries,
                                                        bg_queries,
                                                        src_pcd,
                                                        ret_attn_mask=True,
                                                        fg_query_num_split=fg_object_query_num_split)

                    object_predictions_mask[b].append(outputs_mask)
                    refine_time += 1


            fg_attn_mask, bg_attn_mask = attn_mask.split([fg_queries.shape[0], bg_queries.shape[0]], dim=0)
            pass_num_fg_attn_mask = 0

            for i in range(target_object_id[b]):
                if i+1 == target_object_id[b]:
                    num_fg_attn_mask = fg_queries_per_object[i].shape[0]
                else:
                    pass_num_fg_attn_mask += fg_queries_per_object[i].shape[0]
            fg_attn_mask_f, fg_attn_mask_b = fg_attn_mask.split([pass_num_fg_attn_mask, fg_attn_mask.shape[0] - pass_num_fg_attn_mask], dim=0)
            selected_fg_attn_mask = fg_attn_mask_b[:num_fg_attn_mask]
            selected_fg_attn_mask = torch.cat([selected_fg_attn_mask, bg_attn_mask], dim=0)
            fg_queries_selected = torch.cat([fg_queries_per_object[target_object_id[b] - 1]], dim=0)
            fg_query_pos_selected = torch.cat([fg_query_pos_per_object[target_object_id[b] - 1]], dim=0)            

            for decoder_counter in range(self.num_decoders):
                if self.shared_decoder:
                        decoder_counter = 0
                for i, hlevel in enumerate(self.hlevels):
                    pos_enc = pos_encodings_pcd[hlevel][0][b]

                    output = self.p_c2o_attention[decoder_counter][i](
                        torch.cat([fg_queries_selected, bg_queries],dim=0),
                        src_pcd,
                        memory_mask=selected_fg_attn_mask,
                        memory_key_padding_mask=None,
                        pos=pos_enc,
                        query_pos=torch.cat([fg_query_pos_selected, bg_query_pos], dim=0)
                    )

                    output = self.p_c2c_attention[decoder_counter][i](
                        output,
                        tgt_mask=None,
                        tgt_key_padding_mask=None,
                        query_pos=torch.cat([fg_query_pos_selected, bg_query_pos], dim=0)
                    )

                    queries = self.p_ffn_attention[decoder_counter][i](
                        output
                    )
                    
                    src_pcd = self.p_o2c_attention[decoder_counter][i](
                        src_pcd,
                        queries,
                        memory_mask=None,
                        memory_key_padding_mask=None,
                        pos=torch.cat([fg_query_pos_selected, bg_query_pos], dim=0),
                        query_pos=pos_enc 
                    ) 
                    fg_queries_selected, bg_queries = queries.split([fg_queries_selected.shape[0], bg_queries.shape[0]], 0)

                    outputs_mask, selected_fg_attn_mask = self.mask_module(
                                                        fg_queries_selected,
                                                        bg_queries,
                                                        src_pcd,
                                                        ret_attn_mask=True,
                                                        fg_query_num_split=part_fg_query_num_split,
                                                        is_part=True)

                    part_predictions_mask[b].append(outputs_mask)


        all_part_predictions_mask = [list(i) for i in zip(*part_predictions_mask)]
        part_predictions_mask = all_part_predictions_mask[-1]
        
        all_object_predictions_mask = [list(i) for i in zip(*object_predictions_mask)]
        object_predictions_mask = all_object_predictions_mask[-1]
        
        out= {
            'part_predictions_mask': part_predictions_mask,
            'object_predictions_mask': object_predictions_mask,
            'backbone_features': pcd_features
        }

        if self.aux:
            out['aux_outputs'] = self._set_aux_loss([
                {
                    'part_predictions_mask': part_mask,
                    'object_predictions_mask': obj_mask
                }
                for obj_mask, part_mask in zip(all_object_predictions_mask[:-1], all_part_predictions_mask[:-1])
            ])
        return out
    
    @torch.jit.unused
    def _set_aux_loss(self, outputs_all_layers):
        return outputs_all_layers


    def mask_module(self, fg_query_feat, bg_query_feat, mask_features, ret_attn_mask=True,
                                fg_query_num_split=None, is_part=False):

        fg_query_feat = self.decoder_norm(fg_query_feat)
        bg_query_feat = self.decoder_norm(bg_query_feat)

        def address_mask(mask_features, fg_query_num_split, fg_mask_embed):
            fg_prods = mask_features @ fg_mask_embed.T
            fg_prods = fg_prods.split(fg_query_num_split, dim=1)

            fg_masks = []
            for fg_prod in fg_prods:
                fg_masks.append(fg_prod.max(dim=-1, keepdim=True)[0])

            return torch.cat(fg_masks, dim=-1)
            
        
        if is_part:
            fg_mask_embed = self.part_mask_embed_head(fg_query_feat)
            bg_mask_embed = self.part_mask_embed_head(bg_query_feat)
        else:
            fg_mask_embed = self.mask_embed_head(fg_query_feat)
            bg_mask_embed = self.mask_embed_head(bg_query_feat)
            
        fg_masks = address_mask(mask_features, fg_query_num_split, fg_mask_embed)
        
        bg_masks = (mask_features @ bg_mask_embed.T).max(dim=-1, keepdim=True)[0]
        output_masks = torch.cat([bg_masks, fg_masks], dim=-1)

        if ret_attn_mask:
            
            output_labels = output_masks.argmax(1)

            bg_attn_mask = ~(output_labels == 0)
            bg_attn_mask = bg_attn_mask.unsqueeze(0).repeat(bg_query_feat.shape[0], 1)
            bg_attn_mask[torch.where(bg_attn_mask.sum(-1) == bg_attn_mask.shape[-1])] = False
            
            fg_attn_mask = []
            for fg_obj_id in range(1, fg_masks.shape[-1]+1):
                fg_obj_mask = ~(output_labels == fg_obj_id)
                fg_obj_mask = fg_obj_mask.unsqueeze(0).repeat(fg_query_num_split[fg_obj_id-1], 1)
                fg_obj_mask[torch.where(fg_obj_mask.sum(-1) == fg_obj_mask.shape[-1])] = False
                fg_attn_mask.append(fg_obj_mask)

            fg_attn_mask = torch.cat(fg_attn_mask, dim=0)
            fg_attn_mask = fg_attn_mask.to(bg_attn_mask.device)
            attn_mask = torch.cat([fg_attn_mask, bg_attn_mask], dim=0)

            return output_masks, attn_mask

        return output_masks





def build_PinPoint3D(args):

    backbone = build_backbone(args)

    model = PinPoint3D(
                    backbone=backbone, 
                    hidden_dim=args.hidden_dim,
                    num_heads=args.num_heads, 
                    dim_feedforward=args.dim_feedforward,
                    shared_decoder=args.shared_decoder,
                    num_decoders=args.num_decoders, 
                    num_bg_queries=args.num_bg_queries,
                    dropout=args.dropout, 
                    pre_norm=args.pre_norm, 
                    positional_encoding_type=args.positional_encoding_type,
                    normalize_pos_enc=args.normalize_pos_enc,
                    hlevels=args.hlevels, 
                    voxel_size=args.voxel_size,
                    gauss_scale=args.gauss_scale,
                    aux=args.aux
                    )

    return model