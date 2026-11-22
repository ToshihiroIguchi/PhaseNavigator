/**
 * Calculation worker of the static edition.
 *
 * Runs Pyodide (Python compiled to WebAssembly) and the `phasecore` package in a
 * background thread, so the page stays responsive during a calculation.
 *
 * Messages from the page:
 *   {type: 'init', pyodideUrl, pyodideSri, siteBase}
 *   {type: 'run', id, functional, dataFile, payload}
 * Messages to the page:
 *   {type: 'status', id, text}   progress text of request `id`
 *   {type: 'ready'}              the engine is loaded
 *   {type: 'result', id, payload}  parsed answer of `phasecore.runtime.run`
 *   {type: 'error', id, message}   user-facing failure (id is null for start-up errors)
 */
'use strict';

const PYTHON_LIB_DIR = '/home/pyodide/lib';

let siteBase = '';
let runtimePromise = null;
let queue = Promise.resolve();

/**
 * Send a message to the page.
 * @param {Object} message - Structured-clonable message.
 */
function post(message) {
  self.postMessage(message);
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
    response = await fetch(new URL(path, siteBase));
  } catch (networkError) {
    throw new Error(missingMessage);
  }
  if (!response.ok) throw new Error(missingMessage);
  return response;
}

/**
 * Load the Pyodide loader module after checking its SHA-384 integrity hash.
 * (The classic `pyodide.js` refuses to run in a worker, so the ES module build is used.)
 * @param {string} url - Base URL of the pinned Pyodide release (ends with '/').
 * @param {string} sri - Expected integrity value of `pyodide.mjs`.
 * @returns {Promise<function(Object): Promise<Object>>} The `loadPyodide` function.
 * @throws {Error} If the module cannot be fetched or does not match the hash.
 */
async function importPyodideLoader(url, sri) {
  const failure = 'The calculation engine could not be loaded. Check your connection and reload the page.';
  let response;
  try {
    response = await fetch(`${url}pyodide.mjs`, { integrity: sri, mode: 'cors' });
  } catch (error) {
    throw new Error(failure);
  }
  if (!response.ok) throw new Error(failure);
  const blobUrl = URL.createObjectURL(new Blob([await response.text()], { type: 'text/javascript' }));
  try {
    return (await import(blobUrl)).loadPyodide;
  } finally {
    URL.revokeObjectURL(blobUrl);
  }
}

/**
 * Start Pyodide, install numpy and scipy and import the phasecore package.
 * The work is done once; later calls reuse the same runtime.
 * @param {{pyodideUrl: string, pyodideSri: string}} config - Pyodide release to load.
 * @param {function(string): void} onStatus - Receives progress messages.
 * @returns {Promise<Object>} Proxy of the `phasecore.runtime` Python module.
 */
function startRuntime(config, onStatus) {
  if (!runtimePromise) {
    runtimePromise = (async () => {
      onStatus('Loading the calculation engine (first run only)…');
      const loadPyodide = await importPyodideLoader(config.pyodideUrl, config.pyodideSri);
      const pyodide = await loadPyodide({ indexURL: config.pyodideUrl });
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
 * @param {string} dataFile - File name inside the site's `data/` folder.
 * @param {function(string): void} onStatus - Receives progress messages.
 * @returns {Promise<void>} Resolves when the data is ready.
 */
async function ensureDataset(runtime, functional, dataFile, onStatus) {
  if (runtime.has_dataset(functional)) return;
  onStatus('Loading Materials Project data…');
  const response = await fetchSiteFile(`data/${dataFile}`, `The data file ${dataFile} is missing.`);
  runtime.load_dataset(functional, await readDataText(response));
}

/**
 * Handle one calculation request.
 * @param {{id: number, functional: string, dataFile: string, payload: Object}} request - From the page.
 * @param {Object} config - Pyodide release to load.
 * @returns {Promise<void>} Resolves after the answer has been posted.
 */
async function handleRun(request, config) {
  const onStatus = (text) => post({ type: 'status', id: request.id, text });
  try {
    const runtime = await startRuntime(config, onStatus);
    await ensureDataset(runtime, request.functional, request.dataFile, onStatus);
    onStatus('Calculating the phase diagram…');
    let answer;
    try {
      answer = JSON.parse(runtime.run(JSON.stringify(request.payload)));
    } catch (error) {
      console.error('Calculation failed:', error);
      throw new Error('The calculation failed unexpectedly. Try different formulas or reload the page.');
    }
    if (!answer.ok) throw new Error(answer.error);
    post({ type: 'result', id: request.id, payload: answer.result });
  } catch (error) {
    post({ type: 'error', id: request.id, message: error.message });
  }
}

let config = null;

self.onmessage = (event) => {
  const message = event.data;
  if (message.type === 'init') {
    siteBase = message.siteBase;
    config = { pyodideUrl: message.pyodideUrl, pyodideSri: message.pyodideSri };
    // Warm up right away; failures are reported with the first request.
    startRuntime(config, () => {}).then(() => post({ type: 'ready' })).catch(() => {});
  } else if (message.type === 'run') {
    // One calculation at a time: Python runs synchronously in this thread anyway.
    queue = queue.then(() => handleRun(message, config));
  }
};
