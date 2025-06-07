// This code is designed to be used in an n8n 'Code' node.
// It requires two inputs from previous nodes:
// 1. 'Get Timesheet Data': An array of timesheet entries.
// 2. 'Get Ledger Data': An array of existing ledger entries.

// The n8n Google Sheets node uses the first row as headers by default.
// We will access the data using these headers as keys.
// --- IMPORTANT: These names must EXACTLY match your column headers in Google Sheets. ---
const TIMESHEET_HOURS_COLUMN = 'Total';
const TIMESHEET_PAID_COLUMN = 'Paid? (Pranit to update)';
const LEDGER_BALANCE_COLUMN = 'Running Balance';
// ------------------------------------------------------------------------------------

const timesheetItems = $('Get Timesheet Data').all();
const ledgerItems = $('Get Ledger Data').all();

// 1. Calculate Unpaid Hours from Timesheet by summing the 'Total' for each work entry.
let unpaidHoursSum = 0;
for (const item of timesheetItems) {
  const row = item.json;
  // Use the 'Total' column header to access the data for each entry.
  const totalHoursValue = row[TIMESHEET_HOURS_COLUMN];
  const paidStatus = row[TIMESHEET_PAID_COLUMN];

  // Process only if 'Total' has a value and the row is not paid.
  if (totalHoursValue && String(totalHoursValue).trim() !== '' && paidStatus !== 'Paid') {
    let hours = 0;
    // Check if the value is a time string like "HH:mm:ss"
    if (typeof totalHoursValue === 'string' && totalHoursValue.includes(':')) {
      const timeParts = totalHoursValue.split(':');
      const h = parseInt(timeParts[0], 10) || 0;
      const m = parseInt(timeParts[1], 10) || 0;
      const s = timeParts.length > 2 ? (parseInt(timeParts[2], 10) || 0) : 0;
      hours = h + (m / 60) + (s / 3600);
    }
    // Check if value is a number (like Google Sheets time values, which are fractions of a day)
    else if (typeof totalHoursValue === 'number' && !isNaN(totalHoursValue)) {
      hours = totalHoursValue * 24;
    }
    unpaidHoursSum += hours;
  }
}

// User requested to round up the total hours.
const roundedUpUnpaidHours = Math.ceil(unpaidHoursSum);

// 2. Prepare Ledger Data by finding the last row for running balance calculation.
const lastLedgerRow = ledgerItems.length > 0 ? ledgerItems[ledgerItems.length - 1].json : null;

// 3. Determine the date range for the 'Description' field based on the current date.
const currentDate = new Date();
const year = currentDate.getFullYear();
const month = currentDate.getMonth();
const dayOfMonth = currentDate.getDate();

let startDateObject;

// If running on or before the 15th, the period starts from the 1st of the month.
if (dayOfMonth <= 15) {
  startDateObject = new Date(year, month, 1);
}
// If running after the 15th, the period starts from the 16th.
else {
  startDateObject = new Date(year, month, 16);
}

// Helper to format a Date object to a 'YYYY-MM-DD' string, avoiding timezone issues.
const formatDate = (date) => {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
}

const startDate = formatDate(startDateObject);
const endDate = formatDate(currentDate);

const juliusDescription = `Julius ${startDate} - ${endDate}`;

// 4. Prepare the new row object for the Ledger sheet.
// The keys here ('A', 'B', etc.) should correspond to the columns in the
// "Append to Ledger" Google Sheets node, which likely expects column letters
// since we are providing the values as an array.
const newRow = {};

// A: DC FY
newRow.A = '2024-2025';
// B: Date
newRow.B = endDate;
// C: Description
newRow.C = juliusDescription;
// D: Hours
newRow.D = roundedUpUnpaidHours;
// E: Rate
newRow.E = 4.0625;
// F: Transaction Amount
const amount = parseFloat(newRow.D) * parseFloat(newRow.E);
newRow.F = parseFloat(amount.toFixed(2));
// G: Location
newRow.G = 'Remitly';
// H: Expense or Revenue?
newRow.H = 'Expense';
// I: Ledger Amount
newRow.I = newRow.H === 'Expense' ? -newRow.F : newRow.F;
// J: Running Balance
const lastBalance = lastLedgerRow && lastLedgerRow[LEDGER_BALANCE_COLUMN] ? parseFloat(lastLedgerRow[LEDGER_BALANCE_COLUMN]) : 0;
newRow.J = parseFloat((lastBalance + newRow.I).toFixed(2));

// 5. Return the final object for the next nodes.
return [{
  json: {
    newRowForSheet: Object.values(newRow),
    paymentAmount: newRow.F.toFixed(2),
    recipient: "Julius"
  }
}]; 