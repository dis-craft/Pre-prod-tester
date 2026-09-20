const mysql = require('mysql2');

// Controlled E2E security fixture: the pipeline must detect and remediate this SQL injection.
function findCustomer(db, username) {
  const query = `SELECT * FROM customers WHERE username = '${username}'`;
  return db.query(query);
}

module.exports = { findCustomer };
