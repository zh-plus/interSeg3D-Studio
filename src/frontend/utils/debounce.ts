/**
 * Debounces a function call, delaying its execution until after a specified amount of time has passed
 * @param fn Function to debounce
 * @param ms Time to wait in milliseconds
 * @returns Debounced function
 */
export function debounce<T extends (...args: any[]) => any>(fn: T, ms = 300): (...args: Parameters<T>) => void {
    let timeoutId: ReturnType<typeof setTimeout>;

    return function (this: any, ...args: Parameters<T>): void {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn.apply(this, args), ms);
    };
}

/**
 * Throttles a function call, ensuring it's not called more frequently than the specified interval
 * @param fn Function to throttle
 * @param ms Minimum time between calls in milliseconds
 * @returns Throttled function
 */
export function throttle<T extends (...args: any[]) => any>(fn: T, ms = 300): (...args: Parameters<T>) => void {
    let lastCall = 0;

    return function (this: any, ...args: Parameters<T>): void {
        const now = Date.now();
        if (now - lastCall >= ms) {
            lastCall = now;
            fn.apply(this, args);
        }
    };
}