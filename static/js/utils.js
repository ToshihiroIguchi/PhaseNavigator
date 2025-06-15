/**
 * Utility functions
 */

// Temperature conversion utilities
function kelvinToCelsius(k) {
  return k - 273.15;
}

function celsiusToKelvin(c) {
  return c + 273.15;
}

// Simple encryption/decryption for API key storage
function simpleEncrypt(text) {
  if (!text) return '';
  try {
    const key = 'PhaseNavigatorKey';
    let encrypted = '';
    for (let i = 0; i < text.length; i++) {
      const charCode = text.charCodeAt(i) ^ key.charCodeAt(i % key.length);
      encrypted += charCode.toString(16).padStart(2, '0');
    }
    return encrypted;
  } catch (e) {
    console.error('Encryption failed:', e);
    return '';
  }
}

function simpleDecrypt(encrypted) {
  if (!encrypted) return '';
  try {
    const key = 'PhaseNavigatorKey';
    let decrypted = '';
    for (let i = 0; i < encrypted.length; i += 2) {
      const hexPair = encrypted.substr(i, 2);
      const charCode = parseInt(hexPair, 16) ^ key.charCodeAt((i / 2) % key.length);
      decrypted += String.fromCharCode(charCode);
    }
    return decrypted;
  } catch (e) {
    console.error('Decryption failed:', e);
    return '';
  }
}

// API key management
function saveApiKey(apiKey) {
  if (!apiKey) return;
  try {
    const encrypted = simpleEncrypt(apiKey);
    localStorage.setItem('mp_api_key_encrypted', encrypted);
    console.log('✅ API key saved securely');
  } catch (error) {
    console.error('❌ Failed to save API key:', error);
  }
}

function restoreApiKey() {
  console.log('Attempting to restore API key...');
  try {
    const storedKey = localStorage.getItem('mp_api_key_encrypted');
    if (storedKey) {
      const decryptedKey = simpleDecrypt(storedKey);
      if (decryptedKey && isValidApiKey(decryptedKey)) {
        console.log('✅ API key restored');
        return decryptedKey;
      } else {
        localStorage.removeItem('mp_api_key_encrypted');
        console.log('🗑️ Cleared corrupted stored key');
      }
    }
  } catch (error) {
    console.error('❌ Error restoring API key:', error);
  }
  return null;
}

function isValidApiKey(key) {
  return key && key.length === 32 && /^[A-Za-z0-9]{32}$/.test(key);
}

// Validation utilities
function validateFormulas(formulasText) {
  const formulas = formulasText.split(',').map(f => f.trim()).filter(f => f);
  
  if (formulas.length < 2) {
    throw new Error('At least 2 chemical formulas are required');
  }
  
  if (formulas.length > 4) {
    throw new Error('Maximum 4 formulas allowed');
  }
  
  return formulas;
}

function validateTemperature(temp, isKelvin = true) {
  const numTemp = parseInt(temp, 10);
  
  if (numTemp === 0) return 0;
  
  if (isKelvin) {
    if (numTemp < 300 || numTemp > 2000) {
      throw new Error('Temperature must be 0 K or between 300-2000 K');
    }
  } else {
    if (numTemp < 27 || numTemp > 1727) {
      throw new Error('Temperature must be 0°C or between 27-1727°C');
    }
  }
  
  return numTemp;
}

// Debounce utility
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// Format number with precision
function formatNumber(num, precision = 4) {
  if (num === null || num === undefined) return 'N/A';
  return Number(num).toFixed(precision);
}

// Clean MP ID for linking
function cleanMpId(mpId) {
  if (!mpId || mpId === 'Unknown') return mpId;
  return mpId.replace(/-r2SCAN|-GGA\+U|-scan|-pbe|-hsesol/gi, '');
}

// Get functional suffix from MP ID
function getFunctionalSuffix(mpId) {
  if (!mpId || mpId === 'Unknown') return '';
  const match = mpId.match(/-r2SCAN|-GGA\+U|-scan|-pbe|-hsesol/gi);
  return match ? match[0] : '';
}