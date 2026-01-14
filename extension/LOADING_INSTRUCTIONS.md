# Loading Mobius OS Extension in Chrome

## Important: Load from the CORRECT folder

You must load the extension from the **`dist`** folder, NOT the `extension` folder.

## Steps:

1. **Open Chrome Extensions Page**
   - Go to `chrome://extensions/`
   - Or: Menu → Extensions → Manage Extensions

2. **Enable Developer Mode**
   - Toggle the "Developer mode" switch in the top-right corner

3. **Load Unpacked Extension**
   - Click the "Load unpacked" button
   - Navigate to: `/Users/ananth/Mobius OS/extension/dist`
   - **NOT** `/Users/ananth/Mobius OS/extension`
   - Select the `dist` folder and click "Select"

4. **Verify Extension Loaded**
   - You should see "Mobius OS" in your extensions list
   - Click the extension icon in the toolbar to open the popup

## Troubleshooting

### Error: "Could not load javascript 'content.js'"
- **Solution**: Make sure you're loading from `extension/dist`, not `extension`
- The `dist` folder contains the compiled JavaScript files

### Error: "Could not load manifest"
- **Solution**: Make sure you selected the `dist` folder which contains `manifest.json`
- Don't select the parent `extension` folder

### Extension doesn't appear
- Make sure Developer Mode is enabled
- Check the browser console for errors (F12 → Console)
- Verify the backend server is running on `http://localhost:5001`

## Rebuilding the Extension

If you make changes to the source code:

```bash
cd extension
npm run build
```

Then reload the extension in Chrome (click the reload icon on the extension card).
