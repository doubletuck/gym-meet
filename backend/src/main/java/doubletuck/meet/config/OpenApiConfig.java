package doubletuck.meet.config;

import doubletuck.meet.dto.AthleteResponse;
import doubletuck.meet.dto.AthleteSummaryResponse;
import doubletuck.meet.dto.EventDetailResponse;
import doubletuck.meet.dto.EventSummaryResponse;
import doubletuck.meet.dto.CompetitionResultsResponse;
import doubletuck.meet.dto.CompetitionSummaryResponse;
import io.swagger.v3.oas.models.media.Schema;
import org.jspecify.annotations.Nullable;
import org.springdoc.core.customizers.OpenApiCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.lang.reflect.RecordComponent;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Stream;

@Configuration
public class OpenApiConfig {

    private static final List<Class<?>> RESPONSES = List.of(EventSummaryResponse.class, EventDetailResponse.class,
            CompetitionSummaryResponse.class, CompetitionResultsResponse.class, AthleteSummaryResponse.class,
            AthleteResponse.class);

    /**
     * Describes the read API's responses exactly, so the front end's generated
     * types do too: every field of a response record is always sent, so it is
     * required, and a field marked {@link Nullable} may be null. Without this
     * every field would be optional, and the front end couldn't tell a field
     * that is always there from one that may be missing.
     */
    @Bean
    OpenApiCustomizer requiredAndNullableFields() {
        return openApi -> {
            Map<String, Schema> schemas = openApi.getComponents().getSchemas();
            RESPONSES.stream().flatMap(OpenApiConfig::withNestedRecords).forEach(record -> {
                Schema<?> schema = schemas.get(record.getSimpleName());
                if (schema == null || schema.getProperties() == null) {
                    return;
                }
                List<String> required = new ArrayList<>();
                for (RecordComponent component : record.getRecordComponents()) {
                    Schema<?> property = schema.getProperties().get(component.getName());
                    if (property == null) {
                        continue;
                    }
                    if (component.getAnnotatedType().isAnnotationPresent(Nullable.class)) {
                        schema.getProperties().put(component.getName(), nullable(property));
                    }
                    required.add(component.getName());
                }
                schema.setRequired(required);
            });
        };
    }

    private static Stream<Class<?>> withNestedRecords(Class<?> type) {
        return Stream.concat(Stream.of(type), Stream.of(type.getDeclaredClasses())
                .filter(Class::isRecord)
                .flatMap(OpenApiConfig::withNestedRecords));
    }

    @SuppressWarnings({ "rawtypes", "unchecked" })
    private static Schema<?> nullable(Schema property) {
        if (property.get$ref() != null) {
            return new Schema<>().anyOf(List.of(property, new Schema<>().types(Set.of("null"))));
        }
        Set<String> types = new LinkedHashSet<>();
        if (property.getTypes() != null) {
            types.addAll(property.getTypes());
        } else if (property.getType() != null) {
            types.add(property.getType());
        }
        types.add("null");
        property.setTypes(types);
        return property;
    }
}
