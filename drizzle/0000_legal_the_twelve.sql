CREATE TABLE `cart` (
	`user` text NOT NULL,
	`product` integer NOT NULL,
	`qty` integer NOT NULL,
	PRIMARY KEY(`user`, `product`)
);
--> statement-breakpoint
CREATE TABLE `orders` (
	`id` text PRIMARY KEY NOT NULL,
	`user` text NOT NULL,
	`items` text NOT NULL,
	`total` integer NOT NULL,
	`address` text NOT NULL
);
