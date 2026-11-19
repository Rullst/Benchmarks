package bench;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;

@Controller
public class HtmlController {

    private final FortuneRepository fortunes;

    public HtmlController(FortuneRepository fortunes) {
        this.fortunes = fortunes;
    }

    @GetMapping("/html")
    public String html(Model model) {
        model.addAttribute("name", "World");
        return "hello";
    }

    /** Every fortune (no ORDER BY), plus one added here, sorted by message with String.compareTo. */
    @GetMapping("/fortunes")
    public String fortunes(Model model) {
        List<Fortune> list = new ArrayList<>(fortunes.findAll());
        list.add(new Fortune(0, "Additional fortune added at request time."));
        list.sort(Comparator.comparing(Fortune::getMessage));
        model.addAttribute("fortunes", list);
        return "fortunes";
    }
}
