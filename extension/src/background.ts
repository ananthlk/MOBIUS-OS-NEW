/**
 * Background service worker for Mobius OS extension
 */

chrome.runtime.onInstalled.addListener(() => {
  console.log('[Mobius OS] Extension installed');
});
