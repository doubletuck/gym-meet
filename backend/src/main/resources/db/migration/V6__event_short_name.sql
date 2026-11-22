-- A few words to name an event where its title won't fit, e.g. Euros 2026.
-- Existing events start with their title cut to fit; importing them again sets
-- the short name their manifest gives.

alter table event add column short_name varchar(40);

update event set short_name = left(title, 40);

alter table event alter column short_name set not null;
