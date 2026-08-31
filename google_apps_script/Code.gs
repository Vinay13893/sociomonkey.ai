const WEBHOOK_SECRET = 'REPLACE_WITH_A_LONG_RANDOM_SECRET';
const SPREADSHEET_ID = '1gAqi7WW70nhqdshqWgUOa1bx0phMI8Mng5XK9VJr_4o';

function doGet() {
  return json_({ok: true, service: 'Ganga Realty LMS Sheet Sync'});
}

function doPost(e) {
  try {
    const body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    if (!body.secret || body.secret !== WEBHOOK_SECRET) throw new Error('Unauthorized');
    const sheet = getSheet_(body.sheet_name || 'Master Leads');
    if (body.action === 'ping') return json_({ok: true, message: 'Apps Script connected'});
    const headers = body.headers || [];
    const rows = body.rows || [];
    if (!headers.length) throw new Error('Missing headers');
    if (body.action === 'full_sync') {
      sheet.clearContents();
      sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
      if (rows.length) sheet.getRange(2, 1, rows.length, headers.length).setValues(rows);
      format_(sheet, headers.length);
      return json_({ok: true, synced: rows.length});
    }
    if (body.action === 'upsert') {
      if (!sheet.getLastRow()) sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
      const ids = sheet.getLastRow() > 1
        ? sheet.getRange(2, 1, sheet.getLastRow() - 1, 1).getValues().map((r, i) => [String(r[0]), i + 2]) : [];
      const index = Object.fromEntries(ids);
      rows.forEach(row => {
        const target = index[String(row[0])];
        if (target) sheet.getRange(target, 1, 1, headers.length).setValues([row]);
        else sheet.appendRow(row);
      });
      return json_({ok: true, synced: rows.length});
    }
    throw new Error('Unknown action');
  } catch (err) {
    return json_({ok: false, error: String(err && err.message || err)});
  }
}

function getSheet_(name) {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  return ss.getSheetByName(name) || ss.insertSheet(name);
}

function format_(sheet, columns) {
  sheet.setFrozenRows(1);
  sheet.getRange(1, 1, 1, columns).setFontWeight('bold').setBackground('#1f2937').setFontColor('#ffffff');
  if (sheet.getFilter()) sheet.getFilter().remove();
  sheet.getRange(1, 1, Math.max(sheet.getLastRow(), 1), columns).createFilter();
}

function json_(value) {
  return ContentService.createTextOutput(JSON.stringify(value)).setMimeType(ContentService.MimeType.JSON);
}
