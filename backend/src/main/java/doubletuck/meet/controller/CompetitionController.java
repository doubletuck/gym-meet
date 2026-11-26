package doubletuck.meet.controller;

import doubletuck.meet.dto.CompetitionResultsResponse;
import doubletuck.meet.service.CompetitionResultsService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/competitions")
public class CompetitionController {

    private final CompetitionResultsService competitionResultsService;

    public CompetitionController(CompetitionResultsService competitionResultsService) {
        this.competitionResultsService = competitionResultsService;
    }

    @GetMapping("/{id}/results")
    public ResponseEntity<CompetitionResultsResponse> findResults(@PathVariable Long id) {
        return competitionResultsService.findResults(id)
                .map(PublicResponses::ok)
                .orElseGet(() -> ResponseEntity.notFound().build());
    }
}
