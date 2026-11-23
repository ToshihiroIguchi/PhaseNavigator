/**
 * UI management and interactions
 */

class UIManager {
  constructor() {
    this.isSubmitting = false;
    this.statusTimer = null;
    // The static edition has no API key and runs the calculation in the browser.
    this.isStatic = document.body.dataset.edition === 'static';
    this.elements = this.initializeElements();
    this.initializeEventListeners();
    this.initializeTemperatureControls();
    if (this.isStatic) {
      this.initializeStaticEdition();
    } else {
      this.restoreApiKeyFromStorage();
    }
  }

  initializeElements() {
    return {
      // Form elements
      formulasInput: document.getElementById('formulas'),
      apiInput: document.getElementById('api-key'),
      apiKeyToggle: document.getElementById('api-key-toggle'),
      apiKeyClear: document.getElementById('api-key-clear'),
      apiKeyStatus: document.getElementById('api-key-status'),
      eCutInput: document.getElementById('e-cut'),
      functionalSelect: document.getElementById('functional'),
      nonCommercialToggle: document.getElementById('include-non-commercial'),
      
      // Temperature controls
      tempToggle: document.getElementById('temp-toggle'),
      tempUnitButtons: Array.from(document.querySelectorAll('#temp-unit-group button[data-unit]')),
      tempControls: document.getElementById('temp-controls'),
      tempInput: document.getElementById('temp-input'),
      tempSlider: document.getElementById('temp-slider'),
      tempConversion: document.getElementById('temp-conversion'),
      finalTempInput: document.getElementById('temp'),
      
      // UI elements
      submitBtn: document.getElementById('submit-btn'),
      submitText: document.getElementById('submit-text'),
      submitLoading: document.getElementById('submit-loading'),
      plotDiv: document.getElementById('plot'),
      messageBox: document.getElementById('message'),
      statusBox: document.getElementById('status'),
      statusText: document.getElementById('status-text'),
      statusElapsed: document.getElementById('status-elapsed'),
      emptyState: document.getElementById('empty-state'),
      
      // Phase info elements
      phaseInfoContainer: document.getElementById('phase-info'),
      phaseCount: document.getElementById('phase-count'),
      phaseSummary: document.getElementById('phase-summary'),
      phaseTableBody: document.getElementById('phase-table-body')
    };
  }

  async ensurePlotlyAvailable(maxWait = 5000) {
    const start = Date.now();
    while (typeof Plotly === 'undefined' && (Date.now() - start) < maxWait) {
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    return typeof Plotly !== 'undefined';
  }

  initializeEventListeners() {
    // Form submission
    this.elements.submitBtn.addEventListener('click', () => this.handleSubmit());
    
    // Temperature controls
    this.elements.tempToggle.addEventListener('change', () => this.updateTemperatureControls());
    this.elements.tempUnitButtons.forEach((button) => {
      button.addEventListener('click', () => this.setTemperatureUnit(button.dataset.unit));
    });
    this.elements.tempSlider.addEventListener('input', () => this.syncTemperatureValues());
    this.elements.tempInput.addEventListener('input', () => this.validateTemperatureInput());
    this.elements.tempInput.addEventListener('blur', () => this.validateTemperatureInput());
    
    // API key management (not present in the static edition)
    if (!this.isStatic) {
      this.elements.apiInput.addEventListener('input', debounce(() => this.handleApiKeyChange(), 500));
      this.elements.apiKeyToggle.addEventListener('click', () => this.toggleApiKeyVisibility());
      this.elements.apiKeyClear.addEventListener('click', () => this.handleApiKeyClear());
    }
    
    // Form input changes
    this.elements.formulasInput.addEventListener('input', () => this.handleFormInputChange());
    this.elements.eCutInput.addEventListener('input', () => this.handleFormInputChange());
    this.elements.functionalSelect.addEventListener('change', () => this.handleFormInputChange());
  }

  initializeTemperatureControls() {
    this.elements.tempControls.style.display = 'none';
    this.elements.finalTempInput.value = '0';
    this.tempUnit = 'K'; // Default is Kelvin
    this.elements.tempSlider.value = '300';
    this.elements.tempInput.value = '300';
    this.updateTemperatureDisplay(true); // Kelvin display
    this.updateTemperatureConversion();
    this.updateUnitLabels(true); // Set initial active state
  }

  /**
   * Prepare the static edition: show which data snapshot is bundled, disable the
   * functionals that have no data, and warm up the calculation engine once the
   * user starts typing.
   */
  async initializeStaticEdition() {
    this.elements.formulasInput.addEventListener('focus', () => StaticEngine.preload(), { once: true });
    try {
      const manifest = await StaticEngine.loadManifest();
      const available = Object.keys(manifest.datasets || {});
      const select = this.elements.functionalSelect;
      Array.from(select.options).forEach((option) => {
        option.disabled = !available.includes(option.value);
      });
      if (select.selectedOptions[0] && select.selectedOptions[0].disabled) {
        const firstEnabled = Array.from(select.options).find((option) => !option.disabled);
        if (firstEnabled) select.value = firstEnabled.value;
      }

      const snapshot = document.getElementById('data-snapshot');
      if (snapshot) {
        const built = (manifest.built_at || '').slice(0, 10);
        const version = manifest.database_version ? `database version ${manifest.database_version}, ` : '';
        const scope = Array.isArray(manifest.scope) ? ` Elements covered: ${manifest.scope.join(', ')}.` : '';
        snapshot.textContent = `Data snapshot: ${version}downloaded ${built}.${scope}`;
      }
    } catch (error) {
      this.showError(error.message);
    }
  }

  async restoreApiKeyFromStorage() {
    const restoredKey = await restoreApiKey();
    if (restoredKey && this.elements.apiInput) {
      this.elements.apiInput.value = restoredKey;
      this.setApiKeyStatus('Loaded from this browser (encrypted)');
    }
  }

  /**
   * Show a short status line under the API key field.
   * @param {string} text - Message, or an empty string to clear it.
   */
  setApiKeyStatus(text) {
    this.elements.apiKeyStatus.textContent = text;
  }

  /** Switch the API key field between masked and visible text. */
  toggleApiKeyVisibility() {
    const input = this.elements.apiInput;
    const show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    this.elements.apiKeyToggle.textContent = show ? 'Hide key' : 'Show key';
    this.elements.apiKeyToggle.setAttribute('aria-pressed', String(show));
  }

  /** Forget the stored key and empty the field. */
  async handleApiKeyClear() {
    await clearApiKey();
    this.elements.apiInput.value = '';
    this.setApiKeyStatus('Saved key removed from this browser');
  }

  updateTemperatureControls() {
    const isChecked = this.elements.tempToggle.checked;
    console.log('Temperature toggle changed to:', isChecked);
    
    this.elements.tempControls.style.display = isChecked ? 'block' : 'none';
    this.elements.finalTempInput.value = isChecked ? this.getKelvinValue() : '0';
    
    if (isChecked && !this.elements.tempInput.value) {
      this.elements.tempInput.value = '300';
      this.elements.tempSlider.value = '300';
      this.elements.finalTempInput.value = '300';
    }
    
    // Update unit buttons when controls are shown
    if (isChecked) {
      this.updateUnitLabels(this.isKelvin());
    }
  }

  /**
   * Whether the temperature input is currently in kelvin.
   * @returns {boolean} True for kelvin, false for degrees Celsius.
   */
  isKelvin() {
    return this.tempUnit !== 'C';
  }

  /**
   * Switch the temperature input between kelvin and degrees Celsius.
   * Does nothing when the requested unit is already active.
   * @param {string} unit - 'K' or 'C'.
   */
  setTemperatureUnit(unit) {
    if (unit === this.tempUnit) return;
    this.tempUnit = unit === 'C' ? 'C' : 'K';
    const isKelvin = this.isKelvin();
    this.updateTemperatureInputs(isKelvin);
    this.updateTemperatureDisplay(isKelvin);
    this.updateTemperatureConversion();
    this.updateUnitLabels(isKelvin);
  }

  /**
   * Convert the displayed temperature after the unit toggle was switched.
   * The input still holds the value in the PREVIOUS unit, so it is converted
   * to the new unit (isKelvin === true means we just switched to Kelvin).
   * @param {boolean} isKelvin - True when the new unit is Kelvin.
   */
  updateTemperatureInputs(isKelvin) {
    const currentValue = parseInt(this.elements.tempInput.value, 10) || (isKelvin ? 27 : 300);
    let newValue, newMin, newMax, step;

    if (isKelvin) {
      newValue = celsiusToKelvin(currentValue);
      newMin = 300;
      newMax = 2000;
      step = 10;
    } else {
      newValue = kelvinToCelsius(currentValue);
      newMin = 27;
      newMax = 1727;
      step = 5;
    }

    newValue = Math.round(Math.min(newMax, Math.max(newMin, newValue)));

    // Set the slider bounds before its value so the value is not clamped
    // against the previous unit's range.
    this.elements.tempSlider.min = newMin;
    this.elements.tempSlider.max = newMax;
    this.elements.tempSlider.step = step;
    this.elements.tempInput.value = newValue;
    this.elements.tempSlider.value = newValue;
    
    if (this.elements.tempToggle.checked) {
      this.elements.finalTempInput.value = this.getKelvinValue();
    }
  }

  updateTemperatureDisplay(isKelvin) {
    const unit = isKelvin ? 'K' : '°C';
    document.querySelectorAll('.temp-unit').forEach(el => {
      el.textContent = unit;
    });
  }

  /**
   * Reflect the active unit on the K / °C buttons.
   * @param {boolean} isKelvin - True when kelvin is the active unit.
   */
  updateUnitLabels(isKelvin) {
    this.elements.tempUnitButtons.forEach((button) => {
      const active = (button.dataset.unit === 'K') === isKelvin;
      button.setAttribute('aria-pressed', String(active));
    });
  }

  updateTemperatureConversion() {
    const isKelvin = this.isKelvin();
    const currentValue = parseInt(this.elements.tempInput.value, 10) || 300;
    
    let conversionText;
    if (isKelvin) {
      const celsius = Math.round(kelvinToCelsius(currentValue));
      conversionText = `= ${celsius} °C`;
    } else {
      const kelvin = Math.round(celsiusToKelvin(currentValue));
      conversionText = `= ${kelvin} K`;
    }
    
    this.elements.tempConversion.textContent = conversionText;
  }

  getKelvinValue() {
    const isKelvin = this.isKelvin();
    const currentValue = parseInt(this.elements.tempInput.value, 10) || 300;
    return isKelvin ? currentValue : Math.round(celsiusToKelvin(currentValue));
  }

  syncTemperatureValues() {
    const value = this.elements.tempSlider.value;
    this.elements.tempInput.value = value;
    if (this.elements.tempToggle.checked) {
      this.elements.finalTempInput.value = this.getKelvinValue();
    }
    this.updateTemperatureConversion();
  }

  validateTemperatureInput() {
    const isKelvin = this.isKelvin();
    let value = this.elements.tempInput.value;
    
    if (value === '') {
      value = isKelvin ? '300' : '27';
    }
    
    if (isKelvin) {
      value = Math.min(2000, Math.max(300, parseInt(value, 10) || 300));
    } else {
      value = Math.min(1727, Math.max(27, parseInt(value, 10) || 27));
    }
    
    this.elements.tempInput.value = value;
    this.elements.tempSlider.value = value;
    
    if (this.elements.tempToggle.checked) {
      this.elements.finalTempInput.value = this.getKelvinValue();
    }
    
    this.updateTemperatureConversion();
  }

  async handleApiKeyChange() {
    const apiKey = this.elements.apiInput.value.trim();
    if (!apiKey) {
      await clearApiKey();
      this.setApiKeyStatus('');
      return;
    }
    if (isValidApiKey(apiKey)) {
      const saved = await saveApiKey(apiKey);
      this.setApiKeyStatus(saved ? 'Saved in this browser (encrypted)' : 'Could not save the key in this browser');
    } else {
      this.setApiKeyStatus('Key format looks invalid (letters and digits only, 20+ characters)');
    }
  }

  handleFormInputChange() {
    // Update any UI elements that depend on form state
    console.log('Form input changed');
  }

  /**
   * Toggle the busy state of the submit button.
   * @param {boolean} isLoading - True while a request is in flight.
   */
  setLoadingState(isLoading) {
    this.isSubmitting = isLoading;
    this.elements.submitText.hidden = isLoading;
    this.elements.submitLoading.hidden = !isLoading;
    this.elements.submitBtn.disabled = isLoading;
    this.elements.submitBtn.setAttribute('aria-busy', String(isLoading));
  }

  /**
   * Show an error above the diagram. The previous diagram and phase table are
   * left untouched so a failed request does not discard earlier results.
   * The text is inserted with textContent, never parsed as HTML.
   * @param {string} message - Message to show.
   */
  showError(message) {
    const box = document.createElement('div');
    box.className = 'error-message';
    box.append(createIcon('alert'));
    const text = document.createElement('span');
    text.textContent = message;
    box.append(text);
    this.elements.messageBox.replaceChildren(box);
  }

  /** Remove any message shown by showError. */
  clearMessage() {
    this.elements.messageBox.replaceChildren();
  }

  /**
   * Show the busy panel with a running elapsed-time counter. Only real state is
   * shown (a request is in flight); no fake progress steps.
   */
  showStatus() {
    const start = Date.now();
    this.setStatusText('Fetching data and building the diagram…');
    this.elements.statusElapsed.textContent = '0 s';
    this.elements.statusBox.hidden = false;
    this.elements.plotDiv.classList.add('is-stale');
    this.statusTimer = setInterval(() => {
      this.elements.statusElapsed.textContent = `${Math.round((Date.now() - start) / 1000)} s`;
    }, 1000);
  }

  /**
   * Replace the message of the busy panel.
   * @param {string} text - New message (inserted as plain text).
   */
  setStatusText(text) {
    this.elements.statusText.textContent = text;
  }

  /** Hide the busy panel and stop the elapsed-time counter. */
  hideStatus() {
    clearInterval(this.statusTimer);
    this.statusTimer = null;
    this.elements.statusBox.hidden = true;
    this.elements.plotDiv.classList.remove('is-stale');
  }

  hidePhaseInfo() {
    this.elements.phaseInfoContainer.style.display = 'none';
  }

  /**
   * Create a table cell whose content is always treated as plain text.
   * @param {string} text - Cell text.
   * @param {string} [className] - Optional CSS class list.
   * @returns {HTMLTableCellElement} The new cell.
   */
  createCell(text, className) {
    const td = document.createElement('td');
    if (className) td.className = className;
    td.textContent = text;
    return td;
  }

  /**
   * Create the energy-correction cell with an explanatory tooltip.
   * @param {number} correction - Energy correction in eV.
   * @returns {HTMLTableCellElement} The new cell.
   */
  createCorrectionCell(correction) {
    const td = this.createCell(formatNumber(correction, 4), 'energy-cell');
    td.title = correction !== 0
      ? 'Energy correction for DFT systematic errors'
      : 'No energy correction applied';
    return td;
  }

  /**
   * Create the Materials Project ID cell. Only IDs that match the expected
   * pattern become links; anything else is shown as plain text.
   * @param {string} entryId - Entry ID such as "mp-1234-GGA+U".
   * @returns {HTMLTableCellElement} The new cell.
   */
  createEntryIdCell(entryId) {
    const td = document.createElement('td');
    td.className = 'entry-id-cell';
    const cleanId = cleanMpId(entryId);

    if (!/^(mp|mvc)-\d+$/.test(cleanId || '')) {
      td.textContent = entryId || 'Unknown';
      return td;
    }

    const suffix = getFunctionalSuffix(entryId);
    const link = document.createElement('a');
    link.href = `https://next-gen.materialsproject.org/materials/${cleanId}`;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.title = `View ${cleanId} on Materials Project (computed with ${suffix.replace('-', '') || 'standard functional'})`;
    link.append(cleanId);
    if (suffix) {
      const small = document.createElement('span');
      small.className = 'mp-id-suffix';
      small.textContent = suffix;
      link.append(small);
    }
    td.append(link);
    return td;
  }

  displayPhaseInformation(phaseInfo, metadata) {
    // Show the container
    this.elements.phaseInfoContainer.style.display = 'block';
    
    // Update header
    this.elements.phaseCount.textContent = `(${phaseInfo.length} phases)`;
    
    // Update summary
    const temp = metadata.temperature || 0;
    const tempText = temp === 0 ? '0 K' : `${temp} K (${Math.round(kelvinToCelsius(temp))} °C)`;
    const hasCorrections = phaseInfo.some(phase => phase.correction !== 0);
    const correctionNote = hasCorrections ?
      'Some entries include empirical energy corrections (Materials Project compatibility scheme).' :
      'No empirical energy corrections were applied to these entries.';
    
    const excluded = metadata.excluded_non_commercial || 0;
    let licenseNote;
    if (metadata.include_non_commercial) {
      licenseNote = 'Non-commercial (CC BY-NC 4.0) entries may be included. Use for non-commercial purposes only.';
    } else if (metadata.data) {
      // Static edition: the data was filtered when it was downloaded.
      const retrieved = (metadata.data.retrieved_at || '').slice(0, 10);
      const version = metadata.data.database_version ? `, database version ${metadata.data.database_version}` : '';
      licenseNote = `CC BY 4.0 data only. Materials Project snapshot downloaded ${retrieved}${version}.`;
    } else {
      licenseNote = `CC BY 4.0 data only (${excluded} non-commercial ${excluded === 1 ? 'entry' : 'entries'} excluded).`;
    }

    const summaryLine = (label, text) => {
      const strong = document.createElement('strong');
      strong.textContent = `${label} `;
      return [strong, document.createTextNode(text)];
    };
    this.elements.phaseSummary.replaceChildren(
      ...summaryLine(
        'Calculation Details:',
        `Temperature = ${tempText}, Functional = ${metadata.functional || 'Unknown'}, ` +
        `Energy cutoff = ${metadata.e_cut || 0} eV/atom`
      ),
      document.createElement('br'),
      ...summaryLine('Energy Corrections:', correctionNote),
      document.createElement('br'),
      ...summaryLine('Data License:', licenseNote)
    );
    
    // Clear existing table rows
    this.elements.phaseTableBody.innerHTML = '';
    
    // Populate table
    phaseInfo.forEach((phase) => {
      const row = document.createElement('tr');
      
      // Formation energy color coding
      let formationEnergyClass = 'energy-zero';
      if (phase.formation_energy_per_atom !== null) {
        if (phase.formation_energy_per_atom > 0) {
          formationEnergyClass = 'energy-positive';
        } else if (phase.formation_energy_per_atom < 0) {
          formationEnergyClass = 'energy-negative';
        }
      }
      
      row.append(
        this.createCell(phase.formula, 'formula-cell'),
        this.createCell(phase.composition),
        this.createCell(formatNumber(phase.formation_energy_per_atom, 4), `energy-cell ${formationEnergyClass}`),
        this.createCell(formatNumber(phase.energy_per_atom, 4), 'energy-cell'),
        this.createCorrectionCell(phase.correction),
        this.createEntryIdCell(phase.entry_id)
      );

      this.elements.phaseTableBody.appendChild(row);
    });
    
    console.log('Phase information table displayed');
  }

  /**
   * Validate the form, request the diagram from the API and render it.
   * Errors are shown above the diagram; an earlier successful result stays visible.
   */
  async handleSubmit() {
    if (this.isSubmitting) return;
    this.clearMessage();

    try {
      // Validate inputs
      const formulas = validateFormulas(this.elements.formulasInput.value);
      const eCut = parseFloat(this.elements.eCutInput.value) || 0.2;
      const functional = this.elements.functionalSelect.value;
      const temperature = parseInt(this.elements.finalTempInput.value, 10) || 0;
      let apiKey = '';
      let includeNonCommercial = false;

      if (!this.isStatic) {
        apiKey = this.elements.apiInput.value.trim();
        // The toggle is absent unless the server allows non-commercial data
        includeNonCommercial = Boolean(this.elements.nonCommercialToggle
          && this.elements.nonCommercialToggle.checked);

        if (!apiKey) {
          throw new Error('Materials Project API key is required');
        }

        if (!isValidApiKey(apiKey)) {
          throw new Error('Invalid API key format. Please check your Materials Project API key.');
        }
      }

      // Lock the button before any await so a double click cannot send two requests.
      this.setLoadingState(true);
      this.showStatus();

      if (!this.isStatic) {
        await saveApiKey(apiKey);
      }

      const requestData = {
        f: formulas,
        temp: temperature,
        e_cut: eCut,
        functional: functional,
        include_non_commercial: includeNonCommercial
      };

      const response = await generatePhaseDiagram(requestData, apiKey, (text) => this.setStatusText(text));

      const plotData = response.plot || response;
      const phaseInfo = response.phase_info || [];
      const metadata = response.metadata || {};

      const plotlyAvailable = await this.ensurePlotlyAvailable(5000);
      if (!plotlyAvailable) {
        throw new Error('Plot library loading timeout. Please refresh the page.');
      }

      this.elements.emptyState.hidden = true;
      // The container must be visible before Plotly measures it.
      this.elements.plotDiv.hidden = false;
      Plotly.purge(this.elements.plotDiv);
      Plotly.newPlot(this.elements.plotDiv, plotData.data, plotData.layout, {
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d', 'autoScale2d'],
        displaylogo: false
      });

      if (phaseInfo.length > 0) {
        this.displayPhaseInformation(phaseInfo, metadata);
      } else {
        this.hidePhaseInfo();
      }
    } catch (error) {
      console.error('Error generating phase diagram:', error);
      this.showError(error.message || 'An error occurred while generating the phase diagram');
    } finally {
      this.hideStatus();
      this.setLoadingState(false);
    }
  }
}

// Initialize UI manager when DOM is loaded
let uiManager;
document.addEventListener('DOMContentLoaded', () => {
  uiManager = new UIManager();
  console.log('UI Manager initialized');
});