-- A Superior Jury penalty on a two-vault result as a whole, as printed (negative),
-- already deducted from total_score; neither attempt's score includes it.

alter table score add column combined_sj_penalty double precision;
