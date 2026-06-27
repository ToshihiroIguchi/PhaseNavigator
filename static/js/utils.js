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

// Cryptographically secure storage configuration
const DB_NAME = 'PhaseNavigatorSecureDB';
const STORE_NAME = 'KeyStore';
const KEY_NAME = 'AES_GCM_Key';

// Helper to initialize and retrieve IndexedDB instance
function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    request.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME);
      }
    };
  });
}

// Generate or fetch dynamically created non-extractable AES-GCM key
async function getCryptoKey() {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(STORE_NAME, 'readonly');
    const store = transaction.objectStore(STORE_NAME);
    const request = store.get(KEY_NAME);
    
    request.onerror = () => reject(request.error);
    request.onsuccess = async () => {
      if (request.result) {
        resolve(request.result);
      } else {
        try {
          // Generate 256-bit AES key, non-extractable for high security
          const key = await window.crypto.subtle.generateKey(
            { name: 'AES-GCM', length: 256 },
            false,
            ['encrypt', 'decrypt']
          );
          const writeTx = db.transaction(STORE_NAME, 'readwrite');
          const writeStore = writeTx.objectStore(STORE_NAME);
          writeStore.put(key, KEY_NAME);
          resolve(key);
        } catch (e) {
          reject(e);
        }
      }
    };
  });
}

function bufToHex(buffer) {
  return Array.prototype.map.call(new Uint8Array(buffer), x => ('00' + x.toString(16)).slice(-2)).join('');
}

function hexToBuf(hexString) {
  const bytes = new Uint8Array(hexString.length / 2);
  for (let i = 0; i < hexString.length; i += 2) {
    bytes[i / 2] = parseInt(hexString.substr(i, 2), 16);
  }
  return bytes.buffer;
}

// Securely encrypt data using AES-GCM
async function encryptApiKey(text) {
  if (!text) return '';
  try {
    const key = await getCryptoKey();
    const iv = window.crypto.getRandomValues(new Uint8Array(12)); // 96-bit IV
    const encoder = new TextEncoder();
    const encodedData = encoder.encode(text);
    
    const encrypted = await window.crypto.subtle.encrypt(
      { name: 'AES-GCM', iv: iv },
      key,
      encodedData
    );
    
    return bufToHex(iv.buffer) + ':' + bufToHex(encrypted);
  } catch (e) {
    console.error('Encryption failed:', e);
    return '';
  }
}

// Securely decrypt data using AES-GCM
async function decryptApiKey(encryptedStr) {
  if (!encryptedStr || !encryptedStr.includes(':')) return '';
  try {
    const parts = encryptedStr.split(':');
    const iv = new Uint8Array(hexToBuf(parts[0]));
    const data = hexToBuf(parts[1]);
    
    const key = await getCryptoKey();
    const decrypted = await window.crypto.subtle.decrypt(
      { name: 'AES-GCM', iv: iv },
      key,
      data
    );
    
    const decoder = new TextDecoder();
    return decoder.decode(decrypted);
  } catch (e) {
    console.error('Decryption failed:', e);
    return '';
  }
}

// API key management (async versions)
async function saveApiKey(apiKey) {
  if (!apiKey) return;
  try {
    const encrypted = await encryptApiKey(apiKey);
    localStorage.setItem('mp_api_key_encrypted', encrypted);
    console.log('✅ API key saved securely using AES-GCM');
  } catch (error) {
    console.error('❌ Failed to save API key:', error);
  }
}

async function restoreApiKey() {
  console.log('Attempting to restore API key securely...');
  try {
    const storedKey = localStorage.getItem('mp_api_key_encrypted');
    if (storedKey) {
      const decryptedKey = await decryptApiKey(storedKey);
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
  return key && key.length >= 20 && /^[A-Za-z0-9]+$/.test(key);
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
  return mpId.replace(/-r2SCAN|-GGA\+U|-GGA|-scan|-pbe|-hsesol/gi, '');
}

// Get functional suffix from MP ID
function getFunctionalSuffix(mpId) {
  if (!mpId || mpId === 'Unknown') return '';
  const match = mpId.match(/-r2SCAN|-GGA\+U|-GGA|-scan|-pbe|-hsesol/gi);
  return match ? match[0] : '';
}