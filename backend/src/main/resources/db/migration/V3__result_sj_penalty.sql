-- A penalty on a team's or all-around athlete's result as a whole, as printed
-- (negative), already deducted from total_score.

alter table team_result add column sj_penalty double precision;
alter table all_around_result add column sj_penalty double precision;
