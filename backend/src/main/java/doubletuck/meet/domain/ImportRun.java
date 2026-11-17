package doubletuck.meet.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.ForeignKey;
import jakarta.persistence.Index;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import lombok.ToString;

/**
 * One import of a manifest (one discipline and age category of an event), so
 * what is in the database can be checked against the files it came from.
 */
@Getter
@Setter
@NoArgsConstructor
@ToString(exclude = "event")
@Entity
@Table(name = "import_run", indexes = {
        @Index(name = "ix_import_run_manifest", columnList = "manifest")
})
public class ImportRun extends BaseEntity {

    /** The manifest's file name, e.g. 2026-WORLD-CHAMPIONSHIPS-WAG-SR-IMPORT.json. */
    @Column(name = "manifest", nullable = false, length = 150)
    private String manifest;

    /** Null once the event is deleted. */
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "event_id", foreignKey = @ForeignKey(name = "fk_import_run_event"))
    private Event event;

    @Column(name = "discipline_code", nullable = false, length = 3)
    @Enumerated(EnumType.STRING)
    private Discipline discipline;

    @Column(name = "age_category_code", nullable = false, length = 10)
    @Enumerated(EnumType.STRING)
    private AgeCategory ageCategory;

    /** SHA-256 of the manifest and every file it lists, in order. */
    @Column(name = "content_hash", nullable = false, length = 64)
    private String contentHash;

    /** Whether it replaced an earlier import of the same discipline and age category. */
    @Column(name = "replaced", nullable = false)
    private boolean replaced;

    @Column(name = "warning_count", nullable = false)
    private int warningCount;

    /** The import's report as printed: counts, new athletes and warnings. */
    @Column(name = "report", nullable = false, columnDefinition = "text")
    private String report;
}
