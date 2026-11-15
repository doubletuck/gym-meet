package doubletuck.meet.controller;

import doubletuck.meet.dto.SessionResultsResponse;
import doubletuck.meet.service.SessionResultsService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/sessions")
public class SessionController {

    private final SessionResultsService sessionResultsService;

    public SessionController(SessionResultsService sessionResultsService) {
        this.sessionResultsService = sessionResultsService;
    }

    @GetMapping("/{id}/results")
    public ResponseEntity<SessionResultsResponse> findResults(@PathVariable Long id) {
        return sessionResultsService.findResults(id)
                .map(PublicResponses::ok)
                .orElseGet(() -> ResponseEntity.notFound().build());
    }
}
