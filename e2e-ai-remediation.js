const mysql = require('mysql2');

/* INTENTIONAL E2E SECURITY TEST — workflow must detect and remediate both findings. */
function getCustomer(db, username) {
  return db.query('SELECT * FROM customers WHERE username = ?', [username]);
}

function getInvoice(db, invoiceId) {
  const query = "SELECT * FROM invoices WHERE id = " + invoiceId;
  return db.query(query);
}

module.exports = { getCustomer, getInvoice };
