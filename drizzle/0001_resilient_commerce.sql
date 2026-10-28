CREATE TABLE `cart_state` (
	`user` text PRIMARY KEY NOT NULL,
	`version` integer DEFAULT 0 NOT NULL,
	`coupon` text,
	`updated_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT "cart_state_version_nonnegative" CHECK("cart_state"."version" >= 0)
);
--> statement-breakpoint
CREATE TABLE `checkout_requests` (
	`user` text NOT NULL,
	`request_key` text NOT NULL,
	`fingerprint` text NOT NULL,
	`order_id` text NOT NULL,
	`created_at` text NOT NULL,
	PRIMARY KEY(`user`, `request_key`)
);
--> statement-breakpoint
CREATE UNIQUE INDEX `checkout_order_unique` ON `checkout_requests` (`order_id`);--> statement-breakpoint
CREATE INDEX `checkout_fingerprint` ON `checkout_requests` (`user`,`fingerprint`,`created_at`);--> statement-breakpoint
CREATE TABLE `commerce_guards` (
	`id` text PRIMARY KEY NOT NULL,
	`permitted` integer NOT NULL,
	CONSTRAINT "commerce_precondition" CHECK("commerce_guards"."permitted" = 1)
);
--> statement-breakpoint
CREATE TABLE `commerce_mutations` (
	`user` text NOT NULL,
	`request_key` text NOT NULL,
	`fingerprint` text NOT NULL,
	`created_at` text NOT NULL,
	PRIMARY KEY(`user`, `request_key`)
);
--> statement-breakpoint
CREATE TABLE `coupon_limits` (
	`code` text PRIMARY KEY NOT NULL,
	`max_uses` integer NOT NULL,
	CONSTRAINT "coupon_limits_nonnegative" CHECK("coupon_limits"."max_uses" >= 0)
);
--> statement-breakpoint
CREATE TABLE `coupon_redemptions` (
	`order_id` text PRIMARY KEY NOT NULL,
	`user` text NOT NULL,
	`code` text NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `coupon_redemptions_code` ON `coupon_redemptions` (`code`);--> statement-breakpoint
CREATE UNIQUE INDEX `coupon_once_per_guest` ON `coupon_redemptions` (`user`,`code`) WHERE "coupon_redemptions"."code" IN ('FIRSTBUY','LIMITED20');
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS cart_insert_version AFTER INSERT ON cart BEGIN
  INSERT INTO cart_state(user,version,updated_at) VALUES(NEW.user,1,CURRENT_TIMESTAMP)
  ON CONFLICT(user) DO UPDATE SET version=version+1,updated_at=CURRENT_TIMESTAMP;
END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS cart_update_version AFTER UPDATE OF qty ON cart WHEN NEW.qty<>OLD.qty BEGIN
  INSERT INTO cart_state(user,version,updated_at) VALUES(NEW.user,1,CURRENT_TIMESTAMP)
  ON CONFLICT(user) DO UPDATE SET version=version+1,updated_at=CURRENT_TIMESTAMP;
END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS cart_delete_version AFTER DELETE ON cart BEGIN
  INSERT INTO cart_state(user,version,updated_at) VALUES(OLD.user,1,CURRENT_TIMESTAMP)
  ON CONFLICT(user) DO UPDATE SET version=version+1,updated_at=CURRENT_TIMESTAMP;
END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS limited_coupon_capacity BEFORE INSERT ON coupon_redemptions
WHEN NEW.code='LIMITED20' AND
  (SELECT count(*) FROM coupon_redemptions WHERE code='LIMITED20') >=
  COALESCE((SELECT max_uses FROM coupon_limits WHERE code='LIMITED20'),5)
BEGIN SELECT RAISE(ABORT,'COUPON_LIMIT_REACHED'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS first_order_coupon BEFORE INSERT ON coupon_redemptions
WHEN NEW.code='FIRSTBUY' AND EXISTS(SELECT 1 FROM orders WHERE user=NEW.user)
BEGIN SELECT RAISE(ABORT,'FIRST_ORDER_ONLY'); END;
