chrome.action.onClicked.addListener((tab) => {
    chrome.sidePanel.setOptions({
        tabId: tab.id,
        path: 'index.html',
        enabled: true
    });
    chrome.sidePanel.open({ windowId: tab.windowId });
});
