// Simple utility for performance timing measurements

export class PerformanceLoggerUtil {
    private static timers: Record<string, number> = {};
    private static measurements: Record<string, number[]> = {};
    private static enabled: boolean = true;

    // Start a timer with a given label
    static start(label: string): void {
        if (!this.enabled) return;
        this.timers[label] = performance.now();
    }

    // End a timer and record the elapsed time
    static end(label: string): number {
        if (!this.enabled) return 0;

        const endTime = performance.now();
        const startTime = this.timers[label];

        if (startTime === undefined) {
            console.warn(`Timer "${label}" was never started`);
            return 0;
        }

        const elapsed = endTime - startTime;

        // Store the measurement
        if (!this.measurements[label]) {
            this.measurements[label] = [];
        }
        this.measurements[label].push(elapsed);

        // Log the result
        console.log(`⏱️ ${label}: ${elapsed.toFixed(2)}ms`);

        return elapsed;
    }

    // Get the average time for a specific operation
    static getAverage(label: string): number | null {
        const times = this.measurements[label];
        if (!times || times.length === 0) return null;

        const sum = times.reduce((acc, val) => acc + val, 0);
        return sum / times.length;
    }

    // Log a summary of all measurements
    static logSummary(): void {
        console.group('Performance Summary');

        Object.keys(this.measurements).forEach(label => {
            const times = this.measurements[label];
            const avg = this.getAverage(label);
            const min = Math.min(...times);
            const max = Math.max(...times);

            console.log(`${label}:
        Count: ${times.length}
        Avg: ${avg?.toFixed(2)}ms
        Min: ${min.toFixed(2)}ms
        Max: ${max.toFixed(2)}ms`);
        });

        console.groupEnd();
    }

    // Enable or disable the logger
    static setEnabled(enabled: boolean): void {
        this.enabled = enabled;
    }

    // Reset all measurements
    static reset(): void {
        this.measurements = {};
    }
}