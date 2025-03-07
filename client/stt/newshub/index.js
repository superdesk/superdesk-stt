import angular from "angular";

import NewshubSearchController from "./NewshubSearchController";

export default angular
  .module("stt.newshub", [])
  .controller("NewshubSearchController", NewshubSearchController)
  .run([
    "$templateCache",
    ($templateCache) => {
      $templateCache.put(
        "search-panel-newshub.html",
        require("./views/search-panel.html")
      );
    },
  ]);
