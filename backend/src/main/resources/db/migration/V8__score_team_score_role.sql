-- What a score does for its team: counting toward the team total, dropped from it, or an
-- individual's. Replaces the counts_toward_team_result flag, which couldn't tell the last two apart.

alter table score add column team_score_role_code varchar(20) not null default 'COUNTING';
update score set team_score_role_code = 'DROPPED' where not counts_toward_team_result;
alter table score drop column counts_toward_team_result;
