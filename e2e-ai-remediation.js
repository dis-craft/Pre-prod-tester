const mysql = require('mysql2');

/* INTENTIONAL E2E SECURITY TEST — workflow must detect and remediate both findings. */
// Re-run marker after Gemini retry + full-rescan validation fixes.
function getCustomer(db, username) {
  const query = `SELECT * FROM customers WHERE username = '${username}'`;
  return db.query(query);
}

function getInvoice(db, invoiceId) {
  const query = "SELECT * FROM invoices WHERE id = " + invoiceId;
  return db.query(query);
}

module.exports = { getCustomer, getInvoice };
