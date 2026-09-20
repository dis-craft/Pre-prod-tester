// Live end-to-end security test fixture.
// This file intentionally contains a SQL-injection pattern so the main-branch
// capture -> scan -> Gemini remediation pipeline is exercised.
function lookupLiveUser(db, username) {
  const query = `SELECT * FROM users WHERE username = '${username}'`;
  return db.query(query);
}

module.exports = { lookupLiveUser };
