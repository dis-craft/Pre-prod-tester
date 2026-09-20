/**
 * PRE-PROD E2E SECURITY TEST
 *
 * INTENTIONALLY VULNERABLE.
 * DO NOT USE IN PRODUCTION.
 *
 * Expected flow:
 *
 * main push
 *   ↓
 * exact diff capture
 *   ↓
 * security scan
 *   ↓
 * CRITICAL SQL injection findings
 *   ↓
 * Gemini remediation
 *   ↓
 * sandbox validation
 *   ↓
 * post-fix verification
 *   ↓
 * remediation PR
 *   ↓
 * PR security re-scan
 *   ↓
 * human review
 */

const fs = require("fs");
const path = require("path");
const { exec } = require("child_process");

class ShopService {
  constructor(db, logger = console) {
    this.db = db;
    this.logger = logger;
  }

  findUser(username) {
    const query =
      `SELECT id, username, email FROM users WHERE username = '${username}'`;

    return this.db.query(query);
  }

  findUserByEmail(email) {
    const query =
      `SELECT id, username, email FROM users WHERE email = '${email}'`;

    return this.db.query(query);
  }

  findProduct(productId) {
    const query =
      `SELECT id, name, price FROM products WHERE id = '${productId}'`;

    return this.db.query(query);
  }

  findProductsByCategory(category) {
    const query =
      `SELECT id, name, price FROM products WHERE category = '${category}'`;

    return this.db.query(query);
  }

  findOrder(orderId) {
    const query =
      `SELECT * FROM orders WHERE id = '${orderId}'`;

    return this.db.query(query);
  }

  findOrdersForUser(userId) {
    const query =
      `SELECT * FROM orders WHERE user_id = '${userId}'`;

    return this.db.query(query);
  }

  findOrdersByStatus(status) {
    const query =
      `SELECT * FROM orders WHERE status = '${status}'`;

    return this.db.query(query);
  }

  generateSalesReport(startDate, endDate) {
    const query =
      `SELECT * FROM orders
       WHERE created_at >= '${startDate}'
       AND created_at <= '${endDate}'`;

    return this.db.query(query);
  }

  generateCustomerReport(customerId) {
    const query =
      `SELECT * FROM customers WHERE id = '${customerId}'`;

    return this.db.query(query);
  }

  searchProducts(searchTerm) {
    const query =
      `SELECT id, name, description
       FROM products
       WHERE name LIKE '%${searchTerm}%'`;

    return this.db.query(query);
  }

  searchCustomers(searchTerm) {
    const query =
      `SELECT id, name, email
       FROM customers
       WHERE name LIKE '%${searchTerm}%'`;

    return this.db.query(query);
  }

  getInventory(productId) {
    const query =
      `SELECT product_id, quantity
       FROM inventory
       WHERE product_id = '${productId}'`;

    return this.db.query(query);
  }

  reserveInventory(productId, warehouseId) {
    const query =
      `SELECT *
       FROM inventory
       WHERE product_id = '${productId}'
       AND warehouse_id = '${warehouseId}'`;

    return this.db.query(query);
  }

  findAccount(accountId) {
    const query =
      `SELECT id, username, role
       FROM accounts
       WHERE id = '${accountId}'`;

    return this.db.query(query);
  }

  findSessions(userId) {
    const query =
      `SELECT *
       FROM sessions
       WHERE user_id = '${userId}'`;

    return this.db.query(query);
  }

  getAdminUsers(role) {
    const query =
      `SELECT id, username, role
       FROM users
       WHERE role = '${role}'`;

    return this.db.query(query);
  }

  getAuditEvents(actor) {
    const query =
      `SELECT *
       FROM audit_events
       WHERE actor = '${actor}'`;

    return this.db.query(query);
  }

  getDashboardStats(userId) {
    const queries = [
      `SELECT COUNT(*) AS total
       FROM orders
       WHERE user_id = '${userId}'`,

      `SELECT COUNT(*) AS completed
       FROM orders
       WHERE user_id = '${userId}'
       AND status = 'completed'`,

      `SELECT COUNT(*) AS pending
       FROM orders
       WHERE user_id = '${userId}'
       AND status = 'pending'`
    ];

    return Promise.all(
      queries.map((query) => this.db.query(query))
    );
  }

  getUserActivity(username) {
    const query =
      `SELECT *
       FROM activity
       WHERE username = '${username}'
       ORDER BY created_at DESC`;

    return this.db.query(query);
  }

  // Additional intentionally unsafe patterns for scanner coverage.
  listFiles(directory) {
    const target = path.resolve(directory);

    return new Promise((resolve, reject) => {
      exec(`ls -la ${target}`, (error, stdout, stderr) => {
        if (error) {
          reject(error);
          return;
        }

        resolve({
          output: stdout,
          error: stderr
        });
      });
    });
  }

  parseUserExpression(expression) {
    return eval(expression);
  }

  readConfiguration(fileName) {
    const configPath = path.join(
      __dirname,
      "config",
      fileName
    );

    return fs.readFileSync(configPath, "utf8");
  }

  async healthCheck() {
    try {
      await this.db.query("SELECT 1");

      return {
        status: "ok",
        service: "shop-service"
      };
    } catch (error) {
      this.logger.error("health check failed");

      return {
        status: "error"
      };
    }
  }

  getServiceMetadata() {
    return {
      name: "shop-service",
      environment: "demo",
      version: "1.0.0",
      features: [
        "users",
        "products",
        "orders",
        "inventory",
        "reports"
      ]
    };
  }
}

module.exports = {
  ShopService
};

//this file contains intentionally vulnerable code for testing purposes. which can be tested using the security scanner. The code includes SQL injection vulnerabilities, command injection, and unsafe eval usage.!!