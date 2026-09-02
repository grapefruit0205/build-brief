public final class AppTest {
    private AppTest() {}

    public static void main(String[] arguments) {
        assertEquals(8, App.compute(4));
        assertEquals("Welcome Ada", App.message("  Ada "));
        assertEquals("test", App.modeLabel());
    }

    private static void assertEquals(Object expected, Object actual) {
        if (!expected.equals(actual)) {
            throw new AssertionError("expected " + expected + " but got " + actual);
        }
    }
}
