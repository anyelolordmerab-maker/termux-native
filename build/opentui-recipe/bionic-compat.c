/* Shims para símbolos que Bionic no exporta.
 *
 * - __errno_location: glibc/musl lo usan; Bionic expone __errno().
 * - pthread_tryjoin_np: OpenTUI lo usa en clipboard/host.zig para reap
 *   hilos sin bloquear. Bionic no tiene timedjoin/tryjoin; comprobamos
 *   con pthread_kill(thread, 0) y solo hacemos join si ya terminó.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <pthread.h>

extern int *__errno(void);

int *__errno_location(void) {
    return __errno();
}

int pthread_tryjoin_np(pthread_t thread, void **retval) {
    int rc = pthread_kill(thread, 0);
    if (rc == ESRCH) {
        /* El hilo ya terminó: pthread_join solo recoge el resultado. */
        return pthread_join(thread, retval);
    }
    if (rc == 0) {
        return EBUSY;
    }
    return rc;
}
