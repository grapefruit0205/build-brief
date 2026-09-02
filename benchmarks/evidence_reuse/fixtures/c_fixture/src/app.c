#include "app.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "config.h"
#include "shared.h"


double total_with_tax(double amount) {
    return amount * (1.0 + TAX_RATE);
}


const char *greeting(const char *name) {
    static char greeting_buffer[128];
    snprintf(greeting_buffer, sizeof(greeting_buffer), "Hello, %s!", normalize_name(name));
    return greeting_buffer;
}


const char *fixture_label(void) {
    static char label_buffer[64];
    FILE *handle = fopen("src/data.txt", "r");
    if (handle == NULL) {
        return "missing";
    }
    if (fgets(label_buffer, sizeof(label_buffer), handle) == NULL) {
        fclose(handle);
        return "missing";
    }
    fclose(handle);
    label_buffer[strcspn(label_buffer, "\r\n")] = '\0';
    return label_buffer;
}


const char *mode_label(void) {
    const char *value = getenv("CLICK_BENCH_MODE");
    return value == NULL ? "test" : value;
}
