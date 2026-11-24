/* Shims para simbolos glibc/musl que bionic no exporta.
 * libopentui.so (0.9.4) referencia ambos; sin estos stubs dlopen falla
 * en el telefono con "cannot locate symbol". */
#define _GNU_SOURCE
#include <errno.h>
#include <pthread.h>
#include <time.h>

extern int *__errno(void);
extern int pthread_timedjoin_np(pthread_t, void **, const struct timespec *);

int *__errno_location(void) {
    return __errno();
}

int pthread_tryjoin_np(pthread_t thread, void **retval) {
    struct timespec ts = {0, 0};
    return pthread_timedjoin_np(thread, retval, &ts);
}
