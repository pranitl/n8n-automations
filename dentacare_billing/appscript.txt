function runDaily() {
  var today = new Date();
  var day = today.getDate();
  var lastDayOfMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate();

  Logger.log("--- Daily Trigger Run ---"); // Added log to indicate daily run
  Logger.log("Today's Date: " + today);
  Logger.log("Day of Month: " + day);
  Logger.log("Last Day of Month: " + lastDayOfMonth);

  if (day === 15 || day === lastDayOfMonth) {
    Logger.log("Condition met: Today is the 15th or last day of the month. Executing Ledger Update.");
    dailyUnpaidHoursToLedger(); // Call the main script function when condition is met
  } else {
    Logger.log("Condition not met: Not the 15th or last day of the month. Skipping Ledger Update.");
  }
  Logger.log("--- Daily Trigger Run Completed ---");
}

function dailyUnpaidHoursToLedger() {
  // --- 1. Source Spreadsheet and Sheet (Timesheet) ---
  var sourceSheetURL = "https://docs.google.com/spreadsheets/d/1_5QuQZ55qNYUXCDekfoGBFR2faWPebhUa9XvCxUaAAI/edit?gid=2088379232#gid=2088379232"; // **UPDATED SPREADSHEET URL - CORRECT NOW!**
  var sourceSpreadsheet = SpreadsheetApp.openByUrl(sourceSheetURL);
  var timeSheet = sourceSpreadsheet.getSheetByName("Time sheet");
  if (!timeSheet) {
    Logger.log("Error: 'Time sheet' tab not found in source spreadsheet.");
    return;
  }

  // --- 2. Destination Spreadsheet and Sheet (Ledger) ---
  var destinationSpreadsheet = SpreadsheetApp.openById("1RC27TKSR2FNQ4iGIoB48TcWM_GE01A1GeOnWXvQf1aU");
  var ledgerSheet = destinationSpreadsheet.getSheetByName("Ledger");
  if (!ledgerSheet) {
    Logger.log("Error: 'Ledger' tab not found in destination spreadsheet.");
    return;
  }

  // --- 3. Calculate Sum of Unpaid Hours from "In" (B) and "Out" (C) Times - ITERATION METHOD ---
  var lastRowSource = timeSheet.getLastRow();
  if (lastRowSource < 2) {
    Logger.log("No data found in 'Time sheet' (assuming header in row 1).");
    return;
  }

  var unpaidHoursSum = 0;
  Logger.log("--- Starting Unpaid Hours Calculation from In/Out Times (Iteration Method) ---");
  for (var i = 2; i <= lastRowSource; i++) { // Iterate through each row
    var paidStatusCell = timeSheet.getRange("F" + i);
    var inTimeCell = timeSheet.getRange("B" + i);
    var outTimeCell = timeSheet.getRange("C" + i);

    var inTimeValue = inTimeCell.getValue();
    var outTimeValue = outTimeCell.getValue();

    var isPaid = !!paidStatusCell.getValue(); // Simplified paid status check

    if (!isPaid && inTimeValue instanceof Date && outTimeValue instanceof Date) {
      var timeDiffMs = outTimeValue.getTime() - inTimeValue.getTime();
      var hoursValue = timeDiffMs / (1000 * 60 * 60);
      unpaidHoursSum += hoursValue;
    }
  }
  Logger.log("--- Finished Unpaid Hours Calculation, Total unpaidHoursSum: " + unpaidHoursSum + " ---");

  // --- 4. Get Current Date - MANUAL STRING FORMATTING ---
  var currentDate = new Date();
  var currentYear = currentDate.getFullYear();
  var currentMonth = currentDate.getMonth() + 1; // Month is 0-indexed
  var currentDay = currentDate.getDate();
  var monthStringB = currentMonth < 10 ? "0" + currentMonth : String(currentMonth);
  var dayStringB = currentDay < 10 ? "0" + dayStringB : String(currentDay);
  var formattedDateB = currentYear + "-" + monthStringB + "-" + dayStringB; // MANUAL STRING FORMATTING for Column B
  Logger.log("Formatted Date B (Manual String): " + formattedDateB); // Log for debug


  // --- 5. Input Data in Ledger Tab (Next Available Row) ---
  var lastRowDestination = ledgerSheet.getLastRow();
  var nextRow = lastRowDestination + 1;

  // --- Column A & B: Copy/Current Date (Keep) ---
  if (lastRowDestination > 0) ledgerSheet.getRange("A" + nextRow).setValue(ledgerSheet.getRange("A" + lastRowDestination).getValue());
  ledgerSheet.getRange("B" + nextRow).setValue(formattedDateB);

  // --- Column C: "Julius" Date Range - MANUAL DATE CONSTRUCTION & **EXTREME DEBUGGING - MANUAL STRING FORMATTING** ---
  var startDateForC_YYYY_MM_DD = "";
  var lastJuliusRow = 0;
  var endDateOfLastJulius_DateObject = null; // Initialize as null

  // Find last "Julius" entry
  for (var row = lastRowDestination; row >= 1; row--) {
    if (String(ledgerSheet.getRange("C" + row).getValue()).startsWith("Julius")) {
      lastJuliusRow = row;
      break;
    }
  }

  if (lastJuliusRow > 0) {
    var lastJuliusCValue = ledgerSheet.getRange("C" + lastJuliusRow).getValue();
    var datePart = lastJuliusCValue.substring(lastJuliusCValue.indexOf("- ") + 2);

    Logger.log("--- DATE DEBUGGING START ---"); // **DEBUGGING SECTION START**
    Logger.log("Last Julius C Value: " + lastJuliusCValue);
    Logger.log("Extracted Date Part: " + datePart);

    // **MANUAL DATE CONSTRUCTION - IMPROVED FORMAT HANDLING**
    var datePartsArray;
    var year, month, day;

    if (datePart.includes('-')) { // Assume YYYY-MM-DD format
      datePartsArray = datePart.split('-');
      year = parseInt(datePartsArray[0]);
      month = parseInt(datePartsArray[1]);
      day = parseInt(datePartsArray[2]);
    } else if (datePart.includes('/')) { // Assume M/D or MM/DD format (without year)
      datePartsArray = datePart.split('/');
      month = parseInt(datePartsArray[0]);
      day = parseInt(datePartsArray[1]);
      year = new Date().getFullYear(); // Use current year
    } else {
      Logger.log("ERROR: Unrecognized date format in Julius column: " + datePart);
      startDateForC_YYYY_MM_DD = "Invalid Date Format";
      endDateOfLastJulius_DateObject = null; // Indicate parsing failure
    }


    if (year && month && day) { // Proceed only if year, month, day are successfully parsed
      Logger.log("Parsed Year: " + year + ", Month: " + month + ", Day: " + day); // **DEBUG: Parsed components**

      endDateOfLastJulius_DateObject = new Date(year, month - 1, day); // Construct Date object manually (Month - 1!)
      Logger.log("Parsed endDateOfLastJulius_DateObject (Manual Construction): " + endDateOfLastJulius_DateObject + ", toDateString(): " + endDateOfLastJulius_DateObject.toDateString() + ", toISOString(): " + endDateOfLastJulius_DateObject.toISOString());

      if (isNaN(endDateOfLastJulius_DateObject.getTime())) {
        Logger.log("ERROR: Invalid date parsed (Manual Construction)!");
        startDateForC_YYYY_MM_DD = "Invalid Date";
        endDateOfLastJulius_DateObject = null; //Indicate parsing failure
      } else {
        // **CORRECTED DATE INCREMENT - USING setDate()**
        Logger.log("Before Increment - Date: " + endDateOfLastJulius_DateObject + ", toDateString(): " + endDateOfLastJulius_DateObject.toDateString()); // **DEBUG: Before increment**
        endDateOfLastJulius_DateObject.setDate(endDateOfLastJulius_DateObject.getDate() + 1); // Increment the Date object correctly
        Logger.log("Incremented endDateOfLastJulius_DateObject (Correct Increment): " + endDateOfLastJulius_DateObject + ", toDateString(): " + endDateOfLastJulius_DateObject.toDateString() + ", toISOString(): " + endDateOfLastJulius_DateObject.toISOString());
        Logger.log("Incremented - Year: " + endDateOfLastJulius_DateObject.getFullYear() + ", Month (0-indexed!): " + endDateOfLastJulius_DateObject.getMonth() + ", Day: " + endDateOfLastJulius_DateObject.getDate()); // **DEBUG: After increment - components AND MONTH INDEX**

        // **MANUAL STRING FORMATTING - BYPASS Utilities.formatDate()**
        var nextDay_Year_Manual = endDateOfLastJulius_DateObject.getFullYear();
        var nextDay_Month_Manual = endDateOfLastJulius_DateObject.getMonth() + 1; // Month is 0-indexed, so add 1
        var nextDay_Day_Manual = endDateOfLastJulius_DateObject.getDate();

        // **ZERO-PAD MONTH AND DAY IF NEEDED**
        var monthString = nextDay_Month_Manual < 10 ? "0" + nextDay_Month_Manual : String(nextDay_Month_Manual);
        var dayString = nextDay_Day_Manual < 10 ? "0" + nextDay_Day_Manual : String(nextDay_Day_Manual);

        startDateForC_YYYY_MM_DD = nextDay_Year_Manual + "-" + monthString + "-" + dayString; // **MANUALLY CONSTRUCT YYYY-MM-DD STRING for START DATE**
        Logger.log("Formatted startDateForC_YYYY_MM_DD (Manual String): " + startDateForC_YYYY_MM_DD);

         // **MANUAL STRING FORMATTING for END DATE (formattedDateB - CURRENT DATE)**
        var endDate_Year_Manual = currentDate.getFullYear();
        var endDate_Month_Manual = currentDate.getMonth() + 1;
        var endDate_Day_Manual = currentDate.getDate();
        var endMonthString = endDate_Month_Manual < 10 ? "0" + endDate_Month_Manual : String(endDate_Month_Manual);
        var endDayString = endDate_Day_Manual < 10 ? "0" + endDate_Day_Manual : String(endDate_Day_Manual);
        formattedDateB = endDate_Year_Manual + "-" + endMonthString + "-" + endDayString; // Re-format formattedDateB with manual string formatting
        Logger.log("Re-formatted Date B (Manual String for End Date): " + formattedDateB); // Debug log for end date re-formatting


      }
    }
    Logger.log("--- DATE DEBUGGING END ---"); // **DEBUGGING SECTION END**


  } else {
    // For the ELSE case (no previous Julius entry), we ALSO use manual string formatting for startDateForC_YYYY_MM_DD
        var startYear_Manual = currentDate.getFullYear();
        var startMonth_Manual = currentDate.getMonth() + 1;
        var startDay_Manual = currentDate.getDate();
        var startMonthString = startMonth_Manual < 10 ? "0" + startMonth_Manual : String(startMonthString);
        var startDayString = startDay_Manual < 10 ? "0" + startDay_Manual : String(startDayString);
        startDateForC_YYYY_MM_DD = startYear_Manual + "-" + startMonthString + "-" + startDayString; // MANUAL STRING FORMATTING for start date in ELSE case
        Logger.log("Formatted startDateForC_YYYY_MM_DD (Manual String - ELSE Case): " + startDateForC_YYYY_MM_DD);


    // And ALSO for formattedDateB (end date - current date) - ALREADY formatted above, no need to repeat here.
    endDateOfLastJulius_DateObject = new Date(); // Initialize for no previous entry case (though not directly used for string formatting anymore)
  }


    if (startDateForC_YYYY_MM_DD instanceof Date || startDateForC_YYYY_MM_DD === "Invalid Date" || startDateForC_YYYY_MM_DD === "Invalid Date Format") { // Check for Date object OR "Invalid Date" string OR "Invalid Date Format"
        //NO Conversion needed if it is already a Date object or "Invalid Date" String
    } else {
        startDateForC_YYYY_MM_DD = String(startDateForC_YYYY_MM_DD) //Make sure it is a String for concatenation if it is not a Date object
    }


  var juliusCValue = "Julius " + startDateForC_YYYY_MM_DD + " - " + formattedDateB;
  ledgerSheet.getRange("C" + nextRow).setValue(juliusCValue);
  // --- Columns D-J: Copy/Formulas (Keep) ---
  ledgerSheet.getRange("D" + nextRow).setValue(Math.round(unpaidHoursSum)); // **ROUND TO NEAREST unpaidHoursSum using Math.round()**
  if (lastRowDestination > 0) ledgerSheet.getRange("E" + nextRow).setValue(ledgerSheet.getRange("E" + lastRowDestination).getValue()); else ledgerSheet.getRange("E" + nextRow).setValue(4.06);
  ledgerSheet.getRange("F" + nextRow).setFormula('=D' + nextRow + '*E' + nextRow);
  if (lastRowDestination > 0) ledgerSheet.getRange("G" + nextRow).setValue(ledgerSheet.getRange("G" + lastRowDestination).getValue()); else ledgerSheet.getRange("G" + nextRow).setValue("N/A");
  if (lastRowDestination > 0) ledgerSheet.getRange("H" + nextRow).setValue(ledgerSheet.getRange("H" + lastRowDestination).getValue()); else ledgerSheet.getRange("H" + nextRow).setValue("Expense");
  ledgerSheet.getRange("I" + nextRow).setFormula('=IF(H' + nextRow + '="Expense",F' + nextRow + '="Expense",F' + nextRow + ')');
  ledgerSheet.getRange("J" + nextRow).setFormula('=J' + lastRowDestination + '+I' + nextRow);

  Logger.log("--- Daily unpaid hours and Ledger update completed (EXTREME Date Debugging - MANUAL STRING FORMATTING - BOTH Dates, ROUNDED HOURS to NEAREST, SCHEDULED RUN) ---");
  Logger.log("Date (YYYY-MM-DD): " + formattedDateB + ", Total Unpaid Hours (Rounded to Nearest): " + Math.round(unpaidHoursSum) + ", Julius C Value: " + juliusCValue); // Log rounded hours
}