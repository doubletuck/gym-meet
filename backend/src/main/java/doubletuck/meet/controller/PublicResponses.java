package doubletuck.meet.controller;

import org.springframework.http.CacheControl;
import org.springframework.http.ResponseEntity;

import java.time.Duration;

/**
 * Responses to the public read endpoints. The data changes only when results
 * are imported, so browsers and shared caches may keep a response for a few
 * minutes and then revalidate it against its ETag.
 */
final class PublicResponses {

    static final Duration MAX_AGE = Duration.ofMinutes(5);

    private PublicResponses() {
    }

    static <T> ResponseEntity<T> ok(T body) {
        return ResponseEntity.ok().cacheControl(CacheControl.maxAge(MAX_AGE).cachePublic()).body(body);
    }
}
