-- DataProof synthetic, in-memory DuckDB replay
CREATE TABLE "orders" ("day" DATE NOT NULL CHECK ("day" IN (DATE '2026-01-01', DATE '2026-01-02')), "customer_id" INTEGER NOT NULL CHECK ("customer_id" IN (1, 2)), "amount" INTEGER NOT NULL CHECK ("amount" IN (10)));
DELETE FROM "orders";
INSERT INTO "orders" VALUES (DATE '2026-01-01', 1, 10);
INSERT INTO "orders" VALUES (DATE '2026-01-02', 1, 10);
SELECT CASE WHEN COUNT(*) <= 2 THEN 1 ELSE error('row bound violated') END FROM "orders";
CREATE TABLE d1_view AS SELECT day, COUNT(*) AS order_count, SUM(amount) AS revenue_sum, COUNT(DISTINCT customer_id) AS daily_customers FROM orders GROUP BY day;
CREATE TABLE d1_metric AS SELECT COUNT(DISTINCT customer_id) AS monthly_customers FROM orders;
DELETE FROM "orders";
INSERT INTO "orders" VALUES (DATE '2026-01-01', 1, 10);
INSERT INTO "orders" VALUES (DATE '2026-01-02', 2, 10);
SELECT CASE WHEN COUNT(*) <= 2 THEN 1 ELSE error('row bound violated') END FROM "orders";
CREATE TABLE d2_view AS SELECT day, COUNT(*) AS order_count, SUM(amount) AS revenue_sum, COUNT(DISTINCT customer_id) AS daily_customers FROM orders GROUP BY day;
CREATE TABLE d2_metric AS SELECT COUNT(DISTINCT customer_id) AS monthly_customers FROM orders;
SELECT CASE WHEN (SELECT COUNT(*) FROM ((SELECT * FROM d1_view EXCEPT ALL SELECT * FROM d2_view) UNION ALL (SELECT * FROM d2_view EXCEPT ALL SELECT * FROM d1_view))) = 0 AND (SELECT * FROM d1_metric) IS DISTINCT FROM (SELECT * FROM d2_metric) THEN 'REPLAY_OK' ELSE error('witness assertion failed') END AS replay_status;
