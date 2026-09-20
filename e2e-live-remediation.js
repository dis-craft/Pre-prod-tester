const mysql = require('mysql2');

// Controlled E2E security fixture: the pipeline must detect and remediate this SQL injection.
function findCustomer(db, username) {
  return db.query('SELECT * FROM customers WHERE username = ?', [username]);
}

module.exports = { findCustomer };
