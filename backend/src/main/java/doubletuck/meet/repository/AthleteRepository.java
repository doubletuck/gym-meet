package doubletuck.meet.repository;

import doubletuck.meet.domain.Athlete;
import doubletuck.meet.domain.Discipline;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface AthleteRepository extends JpaRepository<Athlete, Long> {

    Optional<Athlete> findByLicenseNumber(String licenseNumber);

    List<Athlete> findBySurnameIgnoreCaseAndGivenNameIgnoreCaseAndDiscipline(String surname, String givenName,
            Discipline discipline);

    /**
     * Athletes whose name, or a recorded variant of it, contains {@code pattern}
     * ignoring case; {@code pattern} is a lowercase LIKE pattern with {@code \} as escape.
     */
    @Query("select a from Athlete a where lower(concat(a.givenName, ' ', a.surname)) like :pattern escape '\\' "
            + "or exists (select v from AthleteNameVariant v where v.athlete = a "
            + "and lower(concat(v.givenName, ' ', v.surname)) like :pattern escape '\\')")
    List<Athlete> findByNameLike(String pattern);
}
