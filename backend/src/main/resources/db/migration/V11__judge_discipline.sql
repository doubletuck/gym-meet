-- The discipline of a judge's panel, where a competition has both: the Youth Olympic Games'
-- mixed team final has a men's and a women's floor panel (competition-models.md §8). Null
-- elsewhere, where the competition's own discipline says it. The same official can sit on both
-- disciplines' panels, so the discipline is part of a judge's key.

alter table judge add column discipline_code varchar(3);

alter table judge drop constraint uk_judge;
alter table judge add constraint uk_judge unique nulls not distinct
    (competition_id, discipline_code, apparatus_code, function_code, surname, given_name);
