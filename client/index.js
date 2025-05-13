import { startApp } from "superdesk-core/scripts/index";
import newshub from "./stt/newshub";
import "./stt.css";

setTimeout(() => {
  startApp(
    [
      {
        id: "planning-extension",
        load: () => import("superdesk-planning/client/planning-extension"),
      },
    ],
    {}
  );
});

export default angular.module("stt", [newshub.name]);
