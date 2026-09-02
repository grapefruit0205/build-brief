#include "app.h"

#include <math.h>
#include <stdio.h>
#include <string.h>


#define CHECK(expression) do { \
    if (!(expression)) { \
        fprintf(stderr, "check failed: %s\n", #expression); \
        return 1; \
    } \
} while (0)


int main(void) {
    CHECK(fabs(total_with_tax(10.0) - 11.5) < 0.000001);
    CHECK(strcmp(greeting("  Ada "), "Hello, Ada!") == 0);
    CHECK(strcmp(fixture_label(), "control") == 0);
    CHECK(strcmp(mode_label(), "test") == 0);
    return 0;
}
