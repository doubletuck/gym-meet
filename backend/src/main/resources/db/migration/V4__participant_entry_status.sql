-- How an athlete is entered in an event: a competitor, a reserve, or withdrawn
-- (struck through on the entry list).

alter table participant add column entry_status_code varchar(20) not null default 'COMPETITOR';
