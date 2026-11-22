/**
 * Static edition engine (page side).
 *
 * The phase diagram calculation runs in a Web Worker (static/js/calc_worker.js):
 * Pyodide executes the `phasecore` package on pre-downloaded Materials Project data,
 * so no server and no API key are involved and the page stays responsive meanwhile.
 * Only used when the page is built by scripts/build_static_site.py
 * (body[data-edition="static"]).
 */
const StaticEngine = (() => {
  const SCRIPT = document.currentScript;
  const PYODIDE_URL = SCRIPT.dataset.pyodideUrl;
  const PYODIDE_SRI = SCRIPT.dataset.pyodideSri;
  const WORKER_URL = SCRIPT.dataset.workerUrl;

  let manifestPromise = null;
  let worker = null;
  let nextId = 1;
  const pending = new Map();

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
   * Fail every waiting request, for example when the worker cannot run at all.
   * @param {string} message - User-facing error message.
   */
  function failAll(message) {
    for (const request of pending.values()) request.reject(new Error(message));
    pending.clear();
  }

  /**
   * Create the worker on first use and start loading the engine in it.
   * @returns {Worker} The shared calculation worker.
   * @throws {Error} If this browser has no Web Worker support.
   */
  function getWorker() {
    if (worker) return worker;
    if (typeof Worker === 'undefined') {
      throw new Error('This browser cannot run the calculation. Use a current version of Chrome, Edge, Firefox or Safari.');
    }
    worker = new Worker(WORKER_URL, { type: 'module' });
    worker.onmessage = (event) => {
      const message = event.data;
      const request = pending.get(message.id);
      if (!request) return;
      if (message.type === 'status') {
        request.onStatus(message.text);
      } else if (message.type === 'result') {
        pending.delete(message.id);
        request.resolve(message.payload);
      } else if (message.type === 'error') {
        pending.delete(message.id);
        request.reject(new Error(message.message));
      }
    };
    worker.onerror = (event) => {
      // The worker script could not be loaded or crashed: start over on the next request.
      console.error('Calculation worker failed:', event.message || event);
      worker.terminate();
      worker = null;
      failAll(
        'The calculation could not be started. The server may not be sending .js files as JavaScript ' +
        '(see Troubleshooting in the README), or the page is out of date: reload it.'
      );
    };
    worker.postMessage({
      type: 'init',
      pyodideUrl: PYODIDE_URL,
      pyodideSri: PYODIDE_SRI,
      siteBase: document.baseURI
    });
    return worker;
  }

  /**
   * Warm up the engine in the background (for example when the form is first used).
   * Errors are ignored here; they surface when a diagram is requested.
   */
  function preload() {
    try {
      getWorker();
    } catch (error) {
      // Reported when a diagram is requested.
    }
  }

  /**
   * Calculate a phase diagram in the worker.
   * @param {{f: string[], temp: number, e_cut: number, functional: string}} request - Form values.
   * @param {function(string): void} [onStatus] - Receives progress messages.
   * @returns {Promise<Object>} Response shaped like the server's: plot, phase_info, metadata.
   * @throws {Error} With a user-facing message.
   */
  async function generate(request, onStatus = () => {}) {
    const manifest = await loadManifest();
    const info = manifest.datasets && manifest.datasets[request.functional];
    if (!info) throw new Error('No data was built for the selected functional. Choose another one.');

    const engine = getWorker();
    const id = nextId++;
    return new Promise((resolve, reject) => {
      pending.set(id, { resolve, reject, onStatus });
      engine.postMessage({
        type: 'run',
        id,
        functional: request.functional,
        dataFile: info.file,
        payload: {
          formulas: request.f,
          temperature: request.temp,
          e_cut: request.e_cut,
          functional: request.functional
        }
      });
    });
  }

  return { generate, loadManifest, preload };
})();
