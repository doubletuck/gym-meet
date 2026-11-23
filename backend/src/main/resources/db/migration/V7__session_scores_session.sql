-- A session whose standings rank another session's routines, having none of its own: the 2026
-- Asian Championships' team and all-around finals rank the qualification's routines.

alter table session add column scores_session_id bigint;
alter table session add constraint fk_session_scores_session foreign key (scores_session_id) references session (id);
