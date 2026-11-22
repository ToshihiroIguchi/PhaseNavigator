/**
 * Static edition engine.
 *
 * Runs the phase diagram calculation in the browser: Pyodide (Python compiled to
 * WebAssembly) executes the `phasecore` package on pre-downloaded Materials Project
 * data, so no server and no API key are involved. Only used when the page is built
 * by scripts/build_static_site.py (body[data-edition="static"]).
 */
const StaticEngine = (() => {
  const PYODIDE_URL = document.currentScript.dataset.pyodideUrl;
  const PYTHON_LIB_DIR = '/home/pyodide/lib';

  let manifestPromise = null;
  let runtimePromise = null;

  /**
   * Wait until a condition holds.
   * @param {function(): boolean} condition - Polled every 100 ms.
   * @param {number} timeoutMs - Give up after this long.
   * @param {string} message - Error message on timeout.
   * @returns {Promise<void>} Resolves when the condition is true.
   * @throws {Error} With `message` if the timeout is reached.
   */
  async function waitFor(condition, timeoutMs, message) {
    const start = Date.now();
    while (!condition()) {
      if (Date.now() - start > timeoutMs) throw new Error(message);
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }

  /**
   * Fetch a file that belongs to this site.
   * @param {string} path - Path relative to the page.
   * @param {string} missingMessage - Error message if it cannot be fetched.
   * @returns {Promise<Response>} The successful response.
   * @throws {Error} With `missingMessage` on a network or HTTP error.
   */
  async function fetchSiteFile(path, missingMessage) {
    let response;
    try {
      response = await fetch(path);
    } catch (networkError) {
      throw new Error(`${missingMessage} If you opened the page as a local file, serve the folder over HTTP instead.`);
    }
    if (!response.ok) throw new Error(missingMessage);
    return response;
  }

  /**
   * Load the manifest that describes the bundled data files.
   * @returns {Promise<Object>} The parsed manifest.
   */
  function loadManifest() {
    if (!manifestPromise) {
      manifestPromise = fetchSiteFile(
        'data/manifest.json',
        'The data files are missing. Build them with scripts/build_static_data.py (see the README).'
      ).then((response) => response.json()).catch((error) => {
        manifestPromise = null;
        throw error;
      });
    }
    return manifestPromise;
  }

  /**
   * Start Pyodide, install numpy and scipy and import the phasecore package.
   * The work is done once; later calls reuse the same runtime.
   * @param {function(string): void} onStatus - Receives progress messages.
   * @returns {Promise<Object>} Proxy of the `phasecore.runtime` Python module.
   */
  function startRuntime(onStatus) {
    if (!runtimePromise) {
      runtimePromise = (async () => {
        onStatus('Loading the calculation engine (first run only)…');
        await waitFor(
          () => typeof loadPyodide === 'function',
          30000,
          'The calculation engine could not be loaded. Check your connection and reload the page.'
        );
        const pyodide = await loadPyodide({ indexURL: PYODIDE_URL });
        onStatus('Loading numerical libraries…');
        await pyodide.loadPackage(['numpy', 'scipy']);
        onStatus('Loading the phase diagram code…');
        const archive = await fetchSiteFile('phasecore.zip', 'phasecore.zip is missing from this site.');
        pyodide.unpackArchive(await archive.arrayBuffer(), 'zip', { extractDir: PYTHON_LIB_DIR });
        pyodide.runPython(
          `import sys\nif '${PYTHON_LIB_DIR}' not in sys.path:\n    sys.path.insert(0, '${PYTHON_LIB_DIR}')`
        );
        return pyodide.pyimport('phasecore.runtime');
      })().catch((error) => {
        runtimePromise = null;
        throw error;
      });
    }
    return runtimePromise;
  }

  /**
   * Read the text of a data file, unpacking gzip when needed.
   * Servers differ in whether they decompress `.gz` files themselves, so the
   * gzip magic bytes decide.
   * @param {Response} response - Response of the data file.
   * @returns {Promise<string>} The JSON text.
   */
  async function readDataText(response) {
    const bytes = new Uint8Array(await response.arrayBuffer());
    if (bytes[0] === 0x1f && bytes[1] === 0x8b) {
      if (typeof DecompressionStream === 'undefined') {
        throw new Error('This browser cannot unpack the data files. Use a current version of Chrome, Edge, Firefox or Safari.');
      }
      const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
      return new Response(stream).text();
    }
    return new TextDecoder().decode(bytes);
  }

  /**
   * Make sure the dataset of a functional is loaded into the Python runtime.
   * @param {Object} runtime - The `phasecore.runtime` proxy.
   * @param {string} functional - UI functional name.
   * @param {Object} manifest - Parsed manifest.
   * @param {function(string): void} onStatus - Receives progress messages.
   * @returns {Promise<void>} Resolves when the data is ready.
   */
  async function ensureDataset(runtime, functional, manifest, onStatus) {
    if (runtime.has_dataset(functional)) return;
    const info = manifest.datasets && manifest.datasets[functional];
    if (!info) throw new Error('No data was built for the selected functional. Choose another one.');
    onStatus('Loading Materials Project data…');
    const response = await fetchSiteFile(`data/${info.file}`, `The data file ${info.file} is missing.`);
    runtime.load_dataset(functional, await readDataText(response));
  }

  /**
   * Warm up the engine in the background (for example when the form is first used).
   * Errors are ignored here; they surface when a diagram is requested.
   */
  function preload() {
    startRuntime(() => {}).catch(() => {});
  }

  /**
   * Calculate a phase diagram in the browser.
   * @param {{f: string[], temp: number, e_cut: number, functional: string}} request - Form values.
   * @param {function(string): void} [onStatus] - Receives progress messages.
   * @returns {Promise<Object>} Response shaped like the server's: plot, phase_info, metadata.
   * @throws {Error} With a user-facing message.
   */
  async function generate(request, onStatus = () => {}) {
    const manifest = await loadManifest();
    const runtime = await startRuntime(onStatus);
    await ensureDataset(runtime, request.functional, manifest, onStatus);

    onStatus('Calculating the phase diagram…');
    // Let the browser paint the message first: the calculation blocks this thread.
    await new Promise((resolve) => setTimeout(resolve, 30));

    let payload;
    try {
      payload = JSON.parse(runtime.run(JSON.stringify({
        formulas: request.f,
        temperature: request.temp,
        e_cut: request.e_cut,
        functional: request.functional
      })));
    } catch (error) {
      console.error('Calculation failed:', error);
      throw new Error('The calculation failed unexpectedly. Try different formulas or reload the page.');
    }
    if (!payload.ok) throw new Error(payload.error);
    return payload.result;
  }

  return { generate, loadManifest, preload };
})();
