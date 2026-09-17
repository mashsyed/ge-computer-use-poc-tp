/**
 * Google Apps Script Backend for Tax Certificate Computer Use Automation
 */

// ============================================================================
// --- CONFIGURATION CONSTANTS ---
// ============================================================================

var TARGET_FOLDER_ID = '1DYlZzog75i-Ybm9e8bVVf3t24v8NGyNc';
var TEMPLATE_DOC_ID = null;

var SHEET_INTAKE = 'Form Responses 2';
var SHEET_CLIENT_DB = 'Client_Database';
var SHEET_METRICS = 'Metrics_Rollup';

var STATUS_PENDING = 'PENDING';
var STATUS_GENERATING_DOC = 'GENERATING_DOC';
var STATUS_READY_FOR_CRM = 'READY_FOR_CRM';
var STATUS_IN_CRM = 'IN_CRM_PROCESSING';
var STATUS_COMPLETED = 'COMPLETED';
var STATUS_FAILED = 'FAILED_NEEDS_REVIEW';


/**
 * Helper to ensure a valid Google Doc template and Drive folder exist.
 */
function getOrCreateTemplateAndFolder() {
  var folder = null;
  if (TARGET_FOLDER_ID && String(TARGET_FOLDER_ID).trim() !== '' && TARGET_FOLDER_ID !== 'null') {
    try {
      folder = DriveApp.getFolderById(String(TARGET_FOLDER_ID).trim());
    } catch (e) {
      Logger.log('Configured TARGET_FOLDER_ID invalid: ' + e.toString());
    }
  }
  
  if (!folder) {
    var folders = DriveApp.getFoldersByName('Tax_Certificates_Generated');
    folder = folders.hasNext() ? folders.next() : DriveApp.createFolder('Tax_Certificates_Generated');
  }

  var templateFile = null;
  if (TEMPLATE_DOC_ID && String(TEMPLATE_DOC_ID).trim() !== '' && TEMPLATE_DOC_ID !== 'null') {
    try {
      templateFile = DriveApp.getFileById(String(TEMPLATE_DOC_ID).trim());
    } catch (e) {
      Logger.log('Configured TEMPLATE_DOC_ID invalid: ' + e.toString());
    }
  }
  
  if (!templateFile) {
    var files = DriveApp.getFilesByName('Master_Tax_Certificate_Template');
    if (files.hasNext()) {
      templateFile = files.next();
    } else {
      var newDoc = DocumentApp.create('Master_Tax_Certificate_Template');
      var body = newDoc.getBody();
      body.appendParagraph('OFFICIAL TAX CERTIFICATE').setHeading(DocumentApp.ParagraphHeading.HEADING1);
      body.appendParagraph('Date: {{DATE}}');
      body.appendParagraph('Client ID: {{CLIENT_ID}}');
      body.appendParagraph('Email: {{EMAIL}}');
      body.appendParagraph('State Jurisdiction: {{STATE}}');
      body.appendParagraph('Tax Year: {{TAX_YEAR}}');
      body.appendParagraph('Verified Loan Balance: {{LOAN_BALANCE}}');
      body.appendParagraph('\nThis document certifies that the tax standing for the above account has been reviewed and verified.');
      newDoc.saveAndClose();
      templateFile = DriveApp.getFileById(newDoc.getId());
      folder.addFile(templateFile);
    }
  }

  return { templateFile: templateFile, targetFolder: folder };
}


/**
 * Helper to ensure headers exist on the active sheet
 */
function ensureHeaders(sheet) {
  var headers = [
    'Timestamp', 'Client_ID', 'Email', 'State', 'Status', 
    'Doc_URL', 'PDF_Drive_ID', 'Case_ID', 'Error_Log', 'Execution_Duration', 'Email Status'
  ];
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
}


/**
 * Scans sheet and generates PDF certificates for any unprocessed/pending rows
 */
function processPendingIntakeRows() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(SHEET_INTAKE) || ss.getSheetByName("Form Responses 1") || ss.getSheets()[0];
  var data = sheet.getDataRange().getValues();
  
  ensureHeaders(sheet);
  
  var headers = data[0];
  var colClientId = findColumnIndex(headers, ['Client_ID', 'Client ID', 'ClientID']) || 2;
  var colEmail = findColumnIndex(headers, ['Email', 'Email Address']) || 3;
  var colState = findColumnIndex(headers, ['State', 'State Jurisdiction', 'State / Region']) || 4;
  
  for (var i = 1; i < data.length; i++) {
    var row = data[i];
    var status = row[4] ? String(row[4]).trim().toUpperCase() : '';
    
    // Process if status is empty, PENDING, or not set
    if (!status || status === 'PENDING') {
      var targetRow = i + 1;
      var clientId = row[colClientId - 1] ? String(row[colClientId - 1]).trim() : 'CLI-1007';
      var email = row[colEmail - 1] ? String(row[colEmail - 1]).trim() : 'admin@mashsyed.demo.altostrat.com';
      var state = row[colState - 1] ? String(row[colState - 1]).trim() : 'Bogota';
      
      Logger.log('Processing Row ' + targetRow + ' for Client ' + clientId + '...');
      
      sheet.getRange(targetRow, 5).setValue(STATUS_GENERATING_DOC);
      SpreadsheetApp.flush();
      
      try {
        var clientDetails = lookupClientFinancials(clientId);
        var loanBalance = clientDetails.loanBalance ? '$' + Number(clientDetails.loanBalance).toLocaleString() : '$25,000.00';
        var taxYear = String(new Date().getFullYear() - 1);
        
        var resources = getOrCreateTemplateAndFolder();
        var templateFile = resources.templateFile;
        var targetFolder = resources.targetFolder;
        
        var docCopy = templateFile.makeCopy('Tax_Certificate_' + clientId + '_' + new Date().getTime(), targetFolder);
        var docCopyId = docCopy.getId();
        var doc = DocumentApp.openById(docCopyId);
        var body = doc.getBody();
        
        body.replaceText('{{CLIENT_ID}}', clientId);
        body.replaceText('{{EMAIL}}', email);
        body.replaceText('{{STATE}}', state);
        body.replaceText('{{LOAN_BALANCE}}', String(loanBalance));
        body.replaceText('{{TAX_YEAR}}', String(taxYear));
        body.replaceText('{{DATE}}', Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd'));
        
        doc.saveAndClose();
        
        var pdfBlob = docCopy.getAs(MimeType.PDF);
        pdfBlob.setName('Tax_Certificate_' + clientId + '.pdf');
        var pdfFile = targetFolder.createFile(pdfBlob);
        
        var pdfDriveId = pdfFile.getId();
        var pdfDownloadUrl = pdfFile.getDownloadUrl() || pdfFile.getUrl();
        
        DriveApp.getFileById(docCopyId).setTrashed(true);
        
        sheet.getRange(targetRow, 5).setValue(STATUS_READY_FOR_CRM);
        sheet.getRange(targetRow, 6).setValue(pdfDownloadUrl);
        sheet.getRange(targetRow, 7).setValue(pdfDriveId);
        SpreadsheetApp.flush();
        Logger.log('SUCCESS: Generated PDF for row ' + targetRow + ' (Client ' + clientId + ')');
      } catch (err) {
        sheet.getRange(targetRow, 5).setValue(STATUS_FAILED);
        sheet.getRange(targetRow, 9).setValue('Doc Gen Error: ' + err.toString());
        SpreadsheetApp.flush();
      }
    }
  }
}


/**
 * Event-Driven Form Submit Trigger Handler
 */
function onFormSubmit(e) {
  Logger.log('>>> onFormSubmit trigger started execution.');
  processPendingIntakeRows();
}


function findColumnIndex(headers, candidateNames) {
  for (var c = 0; c < headers.length; c++) {
    var headerStr = String(headers[c]).trim().toLowerCase();
    for (var k = 0; k < candidateNames.length; k++) {
      if (headerStr === candidateNames[k].toLowerCase()) {
        return c + 1;
      }
    }
  }
  return null;
}


function lookupClientFinancials(clientId) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(SHEET_CLIENT_DB);
  if (!sheet) {
    return { loanBalance: 25000, creditCardBalance: 1200, standing: 'GOOD_STANDING' };
  }
  
  var data = sheet.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    if (String(data[i][0]).trim().toUpperCase() === String(clientId).trim().toUpperCase()) {
      return {
        clientName: data[i][1],
        creditCardBalance: data[i][2],
        loanBalance: data[i][3],
        standing: data[i][4]
      };
    }
  }
  return { loanBalance: 25000, creditCardBalance: 1200, standing: 'GOOD_STANDING' };
}


function sendDispatchedTaxCertificateEmails() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(SHEET_INTAKE) || ss.getSheetByName("Form Responses 1") || ss.getSheets()[0];
  var data = sheet.getDataRange().getValues();
  
  if (sheet.getRange(1, 11).getValue() === "Column 11" || !sheet.getRange(1, 11).getValue()) {
    sheet.getRange(1, 11).setValue("Email Status");
  }
  
  for (var i = 1; i < data.length; i++) {
    var row = data[i];
    var clientId = row[1];         // Col B: Client_ID
    var email = row[2];            // Col C: Email
    var status = row[4];           // Col E: Status
    var pdfDriveId = row[6];       // Col G: PDF_Drive_ID
    var caseId = row[7];           // Col H: Case_ID
    var emailSentStatus = row[10]; // Col K: Email Status
    
    if (String(status).trim().toUpperCase() === "COMPLETED" && caseId && emailSentStatus !== "SENT") {
      if (!email || email.indexOf("@") === -1) continue;
      
      var subject = "Official Tax Certificate Dispatched - Case " + caseId + " (" + clientId + ")";
      var body = "Dear Client (" + clientId + "),\n\n" +
                 "Your Tax Certificate Request has been processed and approved.\n\n" +
                 "Case Summary:\n" +
                 "- Case ID: " + caseId + "\n" +
                 "- Client ID: " + clientId + "\n" +
                 "- Tax Year: 2025\n\n" +
                 "Attached to this email is your official Tax Certificate PDF document.\n\n" +
                 "Best regards,\n" +
                 "Tax Certificate Operations Team";
      
      var attachments = [];
      if (pdfDriveId) {
        try {
          var file = DriveApp.getFileById(pdfDriveId);
          attachments.push(file.getAs(MimeType.PDF));
        } catch (e) {
          Logger.log("Could not attach PDF: " + e.toString());
        }
      }
      
      try {
        GmailApp.sendEmail(email, subject, body, {
          name: "Tax Certificate Operations",
          from: "admin@mashsyed.demo.altostrat.com",
          attachments: attachments
        });
        sheet.getRange(i + 1, 11).setValue("SENT");
        Logger.log("🎉 Email sent from admin@mashsyed.demo.altostrat.com to " + email + " for Case " + caseId);
      } catch (err) {
        try {
          GmailApp.sendEmail(email, subject, body, {
            name: "Tax Certificate Operations (admin@mashsyed.demo.altostrat.com)",
            attachments: attachments
          });
          sheet.getRange(i + 1, 11).setValue("SENT");
        } catch (fallbackErr) {
          sheet.getRange(i + 1, 11).setValue("ERROR: " + fallbackErr.toString());
        }
      }
    }
  }
}


function doGet(e) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(SHEET_INTAKE) || ss.getSheetByName("Form Responses 1") || ss.getSheets()[0];
  
  processPendingIntakeRows();
  
  var data = sheet.getDataRange().getValues();
  
  if (sheet.getRange(1, 11).getValue() === "Column 11" || !sheet.getRange(1, 11).getValue()) {
    sheet.getRange(1, 11).setValue("Email Status");
  }

  if (!e || !e.parameter) {
    return ContentService.createTextOutput("Apps Script WebApp Endpoint Active.");
  }
  
  var action = e.parameter.action;
  
  if (action === "get_ready_rows") {
    var readyRows = [];
    for (var i = 1; i < data.length; i++) {
      var status = data[i][4] ? String(data[i][4]).trim().toUpperCase() : "";
      if (status === "READY_FOR_CRM") {
        readyRows.push({
          row_index: i + 1,
          client_id: data[i][1],
          email: data[i][2],
          state: data[i][3],
          status: status,
          pdf_drive_id: data[i][6]
        });
      }
    }
    return ContentService.createTextOutput(JSON.stringify(readyRows)).setMimeType(ContentService.MimeType.JSON);
  }
  
  var rowIndex = e.parameter.row_index ? parseInt(e.parameter.row_index) : null;
  var clientId = e.parameter.client_id;
  var caseId = e.parameter.case_id;
  var status = e.parameter.status || "COMPLETED";
  
  if (!clientId || !caseId) {
    return ContentService.createTextOutput("Missing client_id or case_id parameters.");
  }
  
  var targetRowToUpdate = null;

  // 1. Check if row_index was explicitly passed
  if (rowIndex && rowIndex > 1 && rowIndex <= data.length) {
    targetRowToUpdate = rowIndex;
  } else {
    // 2. Search for matching Client_ID that is currently READY_FOR_CRM
    for (var i = 1; i < data.length; i++) {
      var row = data[i];
      var rowStatus = row[4] ? String(row[4]).trim().toUpperCase() : "";
      if (String(row[1]).trim() == String(clientId).trim() && (rowStatus === "READY_FOR_CRM" || rowStatus === "GENERATING_DOC")) {
        targetRowToUpdate = i + 1;
        break;
      }
    }
    // 3. Fallback search by Client_ID
    if (!targetRowToUpdate) {
      for (var i = 1; i < data.length; i++) {
        var row = data[i];
        if (String(row[1]).trim() == String(clientId).trim()) {
          targetRowToUpdate = i + 1;
          break;
        }
      }
    }
  }

  if (targetRowToUpdate) {
    sheet.getRange(targetRowToUpdate, 5).setValue(status); // Col E: Status
    sheet.getRange(targetRowToUpdate, 8).setValue(caseId); // Col H: Case_ID
    sheet.getRange(1, 11).setValue("Email Status");       // Col K Header
    SpreadsheetApp.flush();
    
    try {
      sendDispatchedTaxCertificateEmails();
    } catch (err) {
      Logger.log("Email dispatch warning: " + err);
    }
    
    return ContentService.createTextOutput("✓ SUCCESS: Updated Row " + targetRowToUpdate + " (Client " + clientId + ") with Case " + caseId + " and dispatched email!");
  }
  
  return ContentService.createTextOutput("Client ID " + clientId + " not found in sheet.");
}


/**
 * Run this function ONCE in Apps Script editor to link new Form responses to PDF generation automatically!
 */
function setupFormSubmitTrigger() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'onFormSubmit') {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }
  ScriptApp.newTrigger('onFormSubmit')
      .forSpreadsheet(ss)
      .onFormSubmit()
      .create();
  ScriptApp.newTrigger('onFormSubmit')
      .forSpreadsheet(ss)
      .onChange()
      .create();
  Logger.log('🎉 Setup form submit & change trigger successfully!');
}
