package doubletuck.meet.controller;

import doubletuck.meet.dto.RankingResultsResponse;
import doubletuck.meet.service.RankingResultsService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/rankings")
public class RankingController {

    private final RankingResultsService rankingResultsService;

    public RankingController(RankingResultsService rankingResultsService) {
        this.rankingResultsService = rankingResultsService;
    }

    /** A ranking with no competition of its own (a mixed team's qualification); 404 for any other. */
    @GetMapping("/{id}/results")
    public ResponseEntity<RankingResultsResponse> findResults(@PathVariable Long id) {
        return rankingResultsService.findResults(id)
                .map(PublicResponses::ok)
                .orElseGet(() -> ResponseEntity.notFound().build());
    }
}
