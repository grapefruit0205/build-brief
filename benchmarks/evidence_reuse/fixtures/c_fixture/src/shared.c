#include "shared.h"

#include <ctype.h>
#include <stddef.h>
#include <string.h>


const char *normalize_name(const char *value) {
    static char buffer[128];
    while (isspace((unsigned char)*value)) {
        value++;
    }
    const char *end = value + strlen(value);
    while (end > value && isspace((unsigned char)end[-1])) {
        end--;
    }
    size_t length = (size_t)(end - value);
    if (length >= sizeof(buffer)) {
        length = sizeof(buffer) - 1;
    }
    memcpy(buffer, value, length);
    buffer[length] = '\0';
    return buffer;
}
