"use strict";

const path = require("path");
const fs = require("fs");
const fsPromises = require('fs/promises');
const xlsx = require("xlsx");
const excelPath = path.join("/data/data/excel");

exports.plugin = function (extractionResultData, schemaObj) {
  // ==================== [약제비 plugin 시작] ====================

  var globalItmNo = 1;
  var myResult = new Array();
  var resultData = extractionResultData.result || extractionResultData;
  var hasTableData = Array.isArray(resultData) && resultData.some(item => item.name === "표데이터" && item.data && item.data.length > 0);

  var essentialItems = ["환자성명", "발행일", "병원명", "상호", "약국정보(상호)", "사업자등록번호", "약국정보(사업자등록번호)", "사업장소재지", "약국정보(주소)"];

  var globalAccidentDate = "";

  //조제일자 함수
  resultData.some(function (item) {
    if (item.name === "조제일자" && item.data) {
      for (var i = 0; i < item.data.length; i++) {
        var d = item.data[i];
        if (d.values && d.values.length > 0) {
          globalAccidentDate = getCleanValue("조제일자", d.values[0].label || d.values[0].value || "");
          if (globalAccidentDate) return true;
        }
      }
    } else if (item.name === "표데이터" && item.data) {
      for (var j = 0; j < item.data.length; j++) {
        var tableItem = item.data[j];
        if (tableItem.data) {
          for (var k = 0; k < tableItem.data.length; k++) {
            var row = tableItem.data[k];
            if (row.values) {
              for (var l = 0; l < row.values.length; l++) {
                var cell = row.values[l];
                if (cell.keyLabels && cell.keyLabels[0] === "조제일자") {
                  globalAccidentDate = getCleanValue("조제일자", cell.label || cell.value || "");
                  if (globalAccidentDate) return true;
                }
              }
            }
          }
        }
      }
    }
    return false;
  });

  // 이름 데이터 정의함수
  function getCommonCleanName(val) {
    if (!val || val === "") return "";

    var cleanName = String(val)
      .replace(/[0-9!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/g, "")
      .replace(/[남여]/g, "")
      .replace(/\s+/g, "");

    var len = cleanName.length;
    if (len === 3 || len === 4) {
      return cleanName;
    } else if (len >= 5) {
      return cleanName.substring(0, 3);
    }
    return cleanName;
  }

  // 사업자번호 함수
  function formatBusinessNumber(val) {
    if (!val || val === "") return "";

    var cleanData = String(val).replace(/[^0-9]/g, "");

    if (cleanData.length === 10) {
      return cleanData.replace(/(\d{3})(\d{2})(\d{5})/, "$1-$2-$3");
    }
    return cleanData.length > 0 ? cleanData : "";
  }

  // 미들 추출데이터 이름 정의함수
  function getItemName(cell) {
    if (!cell || !cell.keyLabels || cell.keyLabels.length === 0) return "항목";

    var labels = cell.keyLabels;

    if (labels.indexOf("본인부담") > -1 && labels.indexOf("약제비내역") > -1 && labels.indexOf("카드") > -1) {
      return "비급여본인부담";
    }

    return labels[0];
  }

  // 숫자 정제 및 날짜 형식 정제 함수
  function getCleanValue(itnm, val) {
    var clean = String(val).replace(/[^0-9]/g, "");
    if (itnm.indexOf("일") > -1 && clean.length >= 8) {
      return clean.substring(0, 8);
    }
    return clean;
  }

  // 데이터 가공 함수
  function setResult(itnm, lvlNo, itmNo, rstSeq, hgrkItmNo, itmTpvl, hgrkItnm, cont, confidence, coord, keyLabels) {
    var finalCont = cont;
    var priceKeywords = ["총액", "금액", "부담", "수납", "카드", "현금", "계"];
    var dateKeywords = ["일자", "일"];

    if (itnm === "약국정보(사업자등록번호)") {
      finalCont = formatBusinessNumber(finalCont);
    }

    if (priceKeywords.some(function (k) { return itnm.indexOf(k) > -1; }) ||
      dateKeywords.some(function (k) { return itnm.indexOf(k) > -1; })) {
      finalCont = getCleanValue(itnm, cont);
    }

    var rawLabels = keyLabels || [];
    var labels = rawLabels;
    if (rawLabels.length >= 4) {
      labels = rawLabels.filter(function (l) { return l !== "일부본인부담"; });
    }

    var targetItnm = (itnm === "합계") ? "수납금액" : itnm;
    var targetHgrkItnm = hgrkItnm || "";
    var targetItmTpvl = itmTpvl || "";

    if (itnm === "환자성명") {
      targetItnm = "환자성명";
      finalCont = finalCont.replace(/님|야간|공휴/g, "").replace(/[0-9!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/g, "").trim();
      finalCont = getCommonCleanName(finalCont);
    } else if (labels.length >= 2) {
      targetItmTpvl = (itmTpvl && itmTpvl !== "") ? itmTpvl : labels[labels.length - 1];
      targetHgrkItnm = labels[labels.length - 2] || "";
    } else if (labels.length === 1) {
      if (itmTpvl && itmTpvl !== "") targetItmTpvl = itmTpvl;
    }

    if (labels.indexOf("카드") > -1 && (labels.indexOf("약제비내역") > -1 || itmTpvl === "약제비내역")) {
      targetItnm = "비급여본인부담";
      targetHgrkItnm = "비급여";
    }

    if (targetItnm === "급여본인부담" && targetHgrkItnm === "비급여") {
      targetItnm = "비급여본인부담";
    }

    if ((targetItnm === "본인부담" || targetItnm === "급여본인부담") && targetItnm !== "비급여") {
      targetHgrkItnm = "급여";
    }

    if (targetItnm === "본인부담" && targetHgrkItnm !== "비급여") {
      targetHgrkItnm = "급여";
    }

    var setHeaderMap = {
      "조제일자": "진료.조제일자",
      "약제비총액": "총액",
      "공단부담액": "공단부담액",
      "본인부담": "급여본인부담",
      "비급여": "비급여본인부담",
      "환자부담총액": "환자부담총액",
      "비급여및전액본인부담금": "비급여및전액본인부담금",
    };

    if (setHeaderMap[itnm]) {
      targetItnm = setHeaderMap[itnm];
    }

    // 조제일자 항목
    if (itnm === "조제일자") {
      // targetItnm = "진료.조제일자";
      targetItmTpvl = "";
      targetHgrkItnm = "";
    }

    // 문서 내 위치 정보에 따른 그룹화 코드 설정
    var cont10 = "";
    if (itnm === "환자성명") {
      cont10 = "topInfo";
    } else if (lvlNo === 2) {
      cont10 = "table-contents";
    }

    if (!hasTableData) {
      var exData = ["환자성명", "약국정보(주소)", "약국정보(사업자등록번호)", "약국정보(상호)", "병원명", "발행일"];
      if (!exData.includes(itnm)) {
        cont10 = "table-contents";
      }
    }

    var resultObj = {
      img_extc_itnm: targetItnm,
      lvl_no: 1,
      extc_itm_no: itmNo,
      extc_rst_seq: rstSeq,
      hgrk_extc_itm_no: 0,
      extc_itm_tpvl: targetItmTpvl,
      extc_rst_cont01: finalCont,
      extc_rst_cont09: targetHgrkItnm,
      extc_rst_cont10: cont10,
      self_rlbtr_vl: confidence,
      extc_rst_img_crdn_vl: coord,
      acd_ogtdt: globalAccidentDate
    };

    return resultObj;
  }

  // ---------------------------------------------------------
  //  표 데이터 처리
  // --------------------------------------------------------
  if (hasTableData) {

    resultData.forEach(function (item) {
      if (!item || !item.data || !Array.isArray(item.data)) return;
      if (essentialItems.indexOf(item.name) >= 0) {
        item.data.forEach(function (d) {
          if (d.values && d.values.length > 0) {
            var mergedLabel = "";
            d.values.forEach(function (v) { var val = v.label || v.value || ""; if (val && val !== "원") mergedLabel += (mergedLabel === "" ? "" : " ") + val; });
            if (mergedLabel !== "") myResult.push(setResult(item.name, 1, globalItmNo++, 0, 0, "", "", mergedLabel, d.values[0].confidence, d.values[0].coordinates, d.keyLabels));
          }
        });
      }
    });

    resultData.forEach(function (item) {
      if (item.name === "표데이터") {
        item.data.forEach(function (d) {
          if (d.values) {
            d.values.forEach(function (row) {
              var rowMap = {};
              var currentRowItmNo = globalItmNo++;
              var currentSeq = 1;
              var paymentDetailsTemp = [];

              row.relativeValueInfo.forEach(function (cell) {
                var itm = getItemName(cell);
                var val = cell.label || cell.value || "";

                if (val && val !== "원") {

                  var labels = cell.keyLabels || [];
                  if (itm === "본인부담" && labels.indexOf("약제비내역") > -1 && labels.indexOf("카드") > -1) {
                    itm = "비급여본인부담";
                  }

                  var res = setResult(itm, 2, currentRowItmNo, 0, 0, "", "", val, cell.confidence, cell.coordinates, cell.keyLabels);

                  if (["카드", "현금", "현금영수증"].indexOf(res.img_extc_itnm) > -1) {
                    paymentDetailsTemp.push(res);
                  } else {
                    res.extc_rst_seq = currentSeq++;
                    myResult.push(res);
                  }

                  var cleanVal = Number(getCleanValue(itm, val)) || 0;
                  if (res.img_extc_itnm === "본인부담" && res.extc_rst_cont09 === "비급여") {
                    rowMap["비급여본인부담"] = (rowMap["비급여본인부담"] || 0) + cleanVal;
                  } else if (res.img_extc_itnm === "비급여본인부담") {
                    rowMap["비급여본인부담"] = (rowMap["비급여본인부담"] || 0) + cleanVal;
                  } else if (res.img_extc_itnm === "전액본인부담") {
                    rowMap["전액본인부담"] = (rowMap["전액본인부담"] || 0) + cleanVal;
                  }
                  if (["카드", "현금", "현금영수증"].indexOf(res.img_extc_itnm) > -1) {
                    rowMap[res.img_extc_itnm] = (rowMap[res.img_extc_itnm] || 0) + cleanVal;
                  }
                }
              });

              var nS = (rowMap["비급여본인부담"] || 0) + (rowMap["전액본인부담"] || 0);
              myResult.push(setResult("비급여및전액본인부담금", 2, currentRowItmNo, currentSeq++, 0, "약제비내역", "", String(nS), 1, []));

              paymentDetailsTemp.forEach(function (p) {
                p.extc_rst_seq = currentSeq++;
                myResult.push(p);
              });

              var pS = (rowMap["카드"] || 0) + (rowMap["현금"] || 0) + (rowMap["현금영수증"] || 0);
              if (pS > 0) myResult.push(setResult("수납금액", 2, currentRowItmNo, currentSeq++, 0, "소득공제", "", String(pS), 1, []));
            });
          }
        });
      }
    });

  }
  // ---------------------------------------------------------
  //  단일 데이터 처리
  // ---------------------------------------------------------
  else {
    var valMap = {};
    var priceItems = ["약제비총액", "본인부담", "공단부담액", "비급여", "전액본인부담금", "수납금액", "카드", "현금", "현금영수증", "합계", "비급여및전액본인부담금", "환자부담총액"];
    var incomeTaxCategoryItems = ["카드", "현금", "현금영수증", "합계", "수납금액"];
    var independentItems = ["환자성명", "약국정보(주소)", "약국정보(사업자등록번호)", "약국정보(상호)", "병원명", "발행일"];
    
    var singlePaymentTemp = []; 
    var myRstSeq = 1;

    var processItem = function (item, isIndependent) {
      if (!item || !item.data || !Array.isArray(item.data)) return;
      item.data.forEach(function (d) {
        if (d.values && d.values.length > 0) {
		
          var finalVal = ""; var finalConf = 0; var finalCoords = [];
          var targetObj = d.values[0];
          if (priceItems.indexOf(item.name) >= 0) {
            for (var i = d.values.length - 1; i >= 0; i--) {
              var tempVal = d.values[i].label || d.values[i].value || "";
              if (/[0-9]/.test(tempVal)) { targetObj = d.values[i]; break; }
            }
            finalVal = targetObj.label || targetObj.value || "";
            finalConf = targetObj.confidence; finalCoords = targetObj.coordinates;
          } else {
            d.values.forEach(function (v, vIdx) {
              var val = v.label || v.value || "";
              if (val && val !== "원") { finalVal += (finalVal === "" ? "" : " ") + val; finalConf += Number(v.confidence) || 0; if (vIdx === 0) finalCoords = v.coordinates; }
            });
            finalConf = finalConf / d.values.length;
          }

          if (finalVal === "" || item.name === "환자성명" || finalVal !== undefined) { // (finalVal !== "" || item.name === "환자성명" 문제있을시 이거사용
            var cleaned = getCleanValue(item.name, finalVal);
            valMap[item.name] = (valMap[item.name] || 0) + (Number(cleaned) || 0);
            
            var targetCategory = (incomeTaxCategoryItems.indexOf(item.name) >= 0) ? "소득공제" : "";
            var currentNo = isIndependent ? globalItmNo++ : globalItmNo;
            
            var isPaymentItem = ["카드", "현금", "현금영수증"].indexOf(item.name) > -1;
            var isTotalItem = ["수납금액", "합계"].indexOf(item.name) > -1;
            
            if (isPaymentItem) {
              singlePaymentTemp.push(setResult(item.name, 1, currentNo, 0, 0, "소득공제대상액", item.name, finalVal, finalConf, finalCoords, d.keyLabels));
            } 
            else if (isTotalItem) {} 
            else {
              var sendSeq = isIndependent ? 0 : myRstSeq++;
              myResult.push(setResult(item.name, 1, currentNo, sendSeq, 0, targetCategory, "", finalVal, finalConf, finalCoords, d.keyLabels));
            }
          }
        }
      });
    };

    resultData.forEach(function (item) { if (independentItems.indexOf(item.name) >= 0) processItem(item, true); });
    resultData.forEach(function (item) { if (independentItems.indexOf(item.name) === -1) processItem(item, false); });

    if (valMap["비급여및전액본인부담금"] === undefined || valMap["비급여및전액본인부담금"] === 0 || valMap["비급여및전액본인부담금"] === "") {
      var totalNS = (valMap["비급여"] || 0) + (valMap["전액본인부담금"] || 0);
      if (totalNS >= 0) {
        myResult.push(setResult("비급여및전액본인부담금", 1, globalItmNo, myRstSeq++, 0, "약제비내역", "", String(totalNS), 1, []));
      }
    }

    var payGroupNo = globalItmNo++; 
    var fixedOrder = ["카드", "현금영수증", "현금"];
    fixedOrder.forEach(function (pName) {
      var found = singlePaymentTemp.find(function(tmp) { return tmp.img_extc_itnm === pName; });
      if (found) {
        found.extc_itm_no = payGroupNo;
        found.extc_rst_seq = myRstSeq++; 
        found.extc_rst_cont09 = "";
        myResult.push(found);
      }
    });

    var totalPS = (valMap["수납금액"] || valMap["합계"] || ((valMap["카드"] || 0) + (valMap["현금"] || 0) + (valMap["현금영수증"] || 0)));
    if (totalPS >= 0) {
      myResult.push(setResult("수납금액", 1, payGroupNo, myRstSeq++, 0, "소득공제", "", String(totalPS), 1, []));
    }
  }

  // ==================== [약제비 plugin 종료] ====================
  extractionResultData.result = myResult;

  return extractionResultData;
};