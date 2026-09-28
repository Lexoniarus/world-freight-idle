/** Release every resource before reporting all shutdown failures.
 * @param {Array<() => void>} releases
 * @returns {void}
 */
export function releaseAll(releases) {
  const errors = [];
  for (const release of releases) {
    try {
      release();
    } catch (error) {
      errors.push(error);
    }
  }
  if (errors.length) throw new AggregateError(errors, "Resource cleanup failed");
}

/** Report cleanup errors without replacing an existing workflow failure.
 * @param {Array<() => void>} releases
 * @returns {void}
 */
export function reportCleanup(releases) {
  try {
    releaseAll(releases);
  } catch (error) {
    console.error("Application cleanup failed", error);
  }
}
