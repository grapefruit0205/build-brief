import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;


public final class App {
    private App() {}

    public static int compute(int value) {
        return value * Config.MULTIPLIER;
    }

    public static String message(String name) {
        return dataPrefix() + " " + Shared.normalize(name);
    }

    public static String modeLabel() {
        String value = System.getenv("CLICK_BENCH_MODE");
        return value == null ? "test" : value;
    }

    private static String dataPrefix() {
        try {
            return Files.readString(Path.of("src", "data.txt")).trim();
        } catch (IOException error) {
            return "missing";
        }
    }
}
