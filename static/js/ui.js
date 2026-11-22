/**
 * UI management and interactions
 */

class UIManager {
  constructor() {
    this.elements = this.initializeElements();
    this.initializeEventListeners();
    this.initializeTemperatureControls();
    this.restoreApiKeyFromStorage();
  }

  initializeElements() {
    return {
      // Form elements
      formulasInput: document.getElementById('formulas'),
      apiInput: document.getElementById('api-key'),
      eCutInput: document.getElementById('e-cut'),
      functionalSelect: document.getElementById('functional'),
      
      // Temperature controls
      tempToggle: document.getElementById('temp-toggle'),
      tempUnitToggle: document.getElementById('temp-unit-toggle'),
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
    this.elements.tempUnitToggle.addEventListener('change', () => this.toggleTemperatureUnit());
    this.elements.tempSlider.addEventListener('input', () => this.syncTemperatureValues());
    this.elements.tempInput.addEventListener('input', () => this.validateTemperatureInput());
    this.elements.tempInput.addEventListener('blur', () => this.validateTemperatureInput());
    
    // API key management
    this.elements.apiInput.addEventListener('input', debounce(() => this.handleApiKeyChange(), 500));
    
    // Form input changes
    this.elements.formulasInput.addEventListener('input', () => this.handleFormInputChange());
    this.elements.eCutInput.addEventListener('input', () => this.handleFormInputChange());
    this.elements.functionalSelect.addEventListener('change', () => this.handleFormInputChange());
  }

  initializeTemperatureControls() {
    this.elements.tempControls.style.display = 'none';
    this.elements.finalTempInput.value = '0';
    this.elements.tempUnitToggle.checked = false; // Default is Kelvin
    this.elements.tempSlider.value = '300';
    this.elements.tempInput.value = '300';
    this.updateTemperatureDisplay(true); // Kelvin display
    this.updateTemperatureConversion();
    this.updateUnitLabels(true); // Set initial active state
  }

  async restoreApiKeyFromStorage() {
    const restoredKey = await restoreApiKey();
    if (restoredKey && this.elements.apiInput) {
      this.elements.apiInput.value = restoredKey;
    }
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
    
    // Update unit labels when controls are shown
    if (isChecked) {
      const isKelvin = !this.elements.tempUnitToggle.checked;
      this.updateUnitLabels(isKelvin);
    }
  }

  toggleTemperatureUnit() {
    const isKelvin = !this.elements.tempUnitToggle.checked;
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

  updateUnitLabels(isKelvin) {
    const kelvinLabel = document.querySelector('.unit-label.kelvin');
    const celsiusLabel = document.querySelector('.unit-label.celsius');
    
    if (kelvinLabel && celsiusLabel) {
      if (isKelvin) {
        kelvinLabel.classList.add('active');
        celsiusLabel.classList.remove('active');
      } else {
        celsiusLabel.classList.add('active');
        kelvinLabel.classList.remove('active');
      }
    }
  }

  updateTemperatureConversion() {
    const isKelvin = !this.elements.tempUnitToggle.checked;
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
    const isKelvin = !this.elements.tempUnitToggle.checked;
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
    const isKelvin = !this.elements.tempUnitToggle.checked;
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
    if (apiKey) {
      if (isValidApiKey(apiKey)) {
        await saveApiKey(apiKey);
      }
    } else {
      localStorage.removeItem('mp_api_key_encrypted');
    }
  }

  handleFormInputChange() {
    // Update any UI elements that depend on form state
    console.log('Form input changed');
  }

  setLoadingState(isLoading) {
    if (isLoading) {
      this.elements.submitText.style.display = 'none';
      this.elements.submitLoading.style.display = 'flex';
      this.elements.submitBtn.disabled = true;
    } else {
      this.elements.submitText.style.display = 'inline';
      this.elements.submitLoading.style.display = 'none';
      this.elements.submitBtn.disabled = false;
    }
  }

  showError(message) {
    // Build the node with textContent so server/user supplied text is never parsed as HTML.
    const box = document.createElement('div');
    box.className = 'error-message';
    const icon = document.createElement('span');
    icon.className = 'error-icon';
    icon.textContent = '⚠️';
    const text = document.createElement('span');
    text.textContent = message;
    box.append(icon, text);
    this.elements.plotDiv.replaceChildren(box);
    this.hidePhaseInfo();
  }

  showLoading() {
    this.elements.plotDiv.innerHTML = `
      <div class="loading">
        <div class="loading-spinner"></div>
        Generating phase diagram...
      </div>
      <div class="progress-steps">
        <div class="progress-step active" id="step-1">
          <div class="progress-step-icon">1</div>
          <span>Validating input formulas...</span>
        </div>
        <div class="progress-step pending" id="step-2">
          <div class="progress-step-icon">2</div>
          <span>Fetching data from Materials Project...</span>
        </div>
        <div class="progress-step pending" id="step-3">
          <div class="progress-step-icon">3</div>
          <span>Building phase diagram...</span>
        </div>
        <div class="progress-step pending" id="step-4">
          <div class="progress-step-icon">4</div>
          <span>Rendering interactive plot...</span>
        </div>
      </div>
    `;
    this.hidePhaseInfo();
  }

  updateProgress(stepNumber) {
    for (let i = 1; i <= stepNumber; i++) {
      const step = document.getElementById(`step-${i}`);
      if (step) {
        step.className = 'progress-step completed';
        step.querySelector('.progress-step-icon').innerHTML = '✓';
      }
    }
    
    const nextStep = document.getElementById(`step-${stepNumber + 1}`);
    if (nextStep) {
      nextStep.className = 'progress-step active';
    }
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
    console.log('📊 Displaying phase information:', phaseInfo);
    
    // Show the container
    this.elements.phaseInfoContainer.style.display = 'block';
    
    // Update header
    this.elements.phaseCount.textContent = `(${phaseInfo.length} phases)`;
    
    // Update summary
    const temp = metadata.temperature || 0;
    const tempText = temp === 0 ? '0 K' : `${temp} K (${Math.round(kelvinToCelsius(temp))} °C)`;
    const hasCorrections = phaseInfo.some(phase => phase.correction !== 0);
    const correctionNote = hasCorrections ? 
      'Some phases include DFT energy corrections.' : 
      'No energy corrections applied (all phases are reference states).';
    
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
      ...summaryLine('Energy Corrections:', correctionNote)
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
    
    console.log('✅ Phase information table displayed');
  }

  async handleSubmit() {
    console.log('🚀 Form submission started');
    
    try {
      // Validate inputs
      const formulas = validateFormulas(this.elements.formulasInput.value);
      const apiKey = this.elements.apiInput.value.trim();
      const eCut = parseFloat(this.elements.eCutInput.value) || 0.2;
      const functional = this.elements.functionalSelect.value;
      const temperature = parseInt(this.elements.finalTempInput.value, 10) || 0;
      
      if (!apiKey) {
        throw new Error('Materials Project API key is required');
      }
      
      if (!isValidApiKey(apiKey)) {
        throw new Error('Invalid API key format. Please check your Materials Project API key.');
      }
      
      // Save API key
      await saveApiKey(apiKey);
      
      // Prepare request data
      const requestData = {
        f: formulas,
        temp: temperature,
        e_cut: eCut,
        functional: functional
      };
      
      console.log('Request data:', requestData);
      
      // Start loading state
      this.setLoadingState(true);
      this.showLoading();
      
      // Make API request with progress updates
      this.updateProgress(1);
      await new Promise(resolve => setTimeout(resolve, 300));
      
      this.updateProgress(2);
      await new Promise(resolve => setTimeout(resolve, 200));
      
      const response = await generatePhaseDiagram(requestData, apiKey);
      
      this.updateProgress(3);
      await new Promise(resolve => setTimeout(resolve, 200));
      
      console.log('Received response:', response);
      
      // Extract plot data and phase info
      const plotData = response.plot || response;
      const phaseInfo = response.phase_info || [];
      const metadata = response.metadata || {};
      
      // Clear existing plot
      this.elements.plotDiv.innerHTML = '';
      
      // Create plot
      // Enhanced Plotly loading check with timeout
      const plotlyAvailable = await this.ensurePlotlyAvailable(5000);
      if (!plotlyAvailable) {
        console.error('Plotly library not loaded within timeout');
        this.showError('Plot library loading timeout. Please refresh the page.');
        return;
      }

      Plotly.newPlot(this.elements.plotDiv, plotData.data, plotData.layout, {
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d', 'autoScale2d'],
        displaylogo: false
      });
      
      this.updateProgress(4);
      
      // Display phase information
      if (phaseInfo && phaseInfo.length > 0) {
        this.displayPhaseInformation(phaseInfo, metadata);
      }
      
      console.log('✅ Phase diagram generated successfully');
      
    } catch (error) {
      console.error('❌ Error generating phase diagram:', error);
      this.showError(error.message || 'An error occurred while generating the phase diagram');
    } finally {
      this.setLoadingState(false);
    }
  }
}

// Initialize UI manager when DOM is loaded
let uiManager;
document.addEventListener('DOMContentLoaded', () => {
  uiManager = new UIManager();
  console.log('✅ UI Manager initialized');
});