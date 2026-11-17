package doubletuck.meet.repository;

import doubletuck.meet.domain.ImportRun;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface ImportRunRepository extends JpaRepository<ImportRun, Long> {

    Optional<ImportRun> findFirstByManifestOrderByIdDesc(String manifest);
}
