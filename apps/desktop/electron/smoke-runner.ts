export async function runDesktopSmoke(
  operation: () => Promise<void>,
  stop: () => Promise<void>,
  reportError: (error: unknown) => void = console.error,
): Promise<number> {
  let exitCode = 0;
  try {
    await operation();
  } catch (error) {
    reportError(error);
    exitCode = 1;
  }
  try {
    await stop();
  } catch (error) {
    reportError(error);
    exitCode = 1;
  }
  return exitCode;
}
