package bench;

import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;

@Controller
public class HtmlController {

    @GetMapping("/html")
    public String html(Model model) {
        model.addAttribute("name", "World");
        return "hello";
    }
}
