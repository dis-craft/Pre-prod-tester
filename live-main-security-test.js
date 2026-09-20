const mysql = require('mysql2');

/*
 * INTENTIONAL SECURITY TEST — DO NOT USE IN PRODUCTION.
 * This commit exercises the main-branch security -> AI-fix -> PR flow.
 */
function findUser(db, username) {
  const query = `SELECT * FROM users WHERE username = '${username}'`;
  return db.query(query);
}

function findEmail(db, email) {
  return db.query("SELECT * FROM users WHERE email = '" + email + "'");
}

function findRole(db, role) {
  const query = `SELECT * FROM roles WHERE name = '${role}'`;
  return db.query(query);
}

module.exports = { findUser, findEmail, findRole };
