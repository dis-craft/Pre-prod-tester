// Fresh SQL injection fixture for the canonical pre-prod pipeline.
function getAccount(db, username) {
  return db.query("SELECT * FROM accounts WHERE username = ?", [username]);
}
module.exports = { getAccount };
