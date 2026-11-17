package doubletuck.meet.controller;

import doubletuck.meet.dto.AthleteResponse;
import doubletuck.meet.dto.AthleteSummaryResponse;
import doubletuck.meet.service.AthleteQueryService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/athletes")
public class AthleteController {

    private final AthleteQueryService athleteQueryService;

    public AthleteController(AthleteQueryService athleteQueryService) {
        this.athleteQueryService = athleteQueryService;
    }

    @GetMapping
    public ResponseEntity<List<AthleteSummaryResponse>> search(@RequestParam String q) {
        return PublicResponses.ok(athleteQueryService.search(q));
    }

    @GetMapping("/{id}")
    public ResponseEntity<AthleteResponse> findAthlete(@PathVariable Long id) {
        return athleteQueryService.findAthlete(id)
                .map(PublicResponses::ok)
                .orElseGet(() -> ResponseEntity.notFound().build());
    }
}
