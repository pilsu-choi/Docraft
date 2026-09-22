// const {Logger}              = require('common/logger');
const {Logger}              = require('/usr/src/app/dist/apps/extn/libs/common/src/logger');

const path = require("path");
const fs = require("fs");
const fsPromises = require("fs/promises");

const xlsx = require("xlsx");
const excelPath = path.join("/data/data/excel");
const valuePath = path.join("/data/data/value");

/**
 * 파일 읽어오기
 * @param {string} path // ./schema.json
 * @returns
 */
exports.readFile = function readFile(path) {
  return JSON.parse(fs.readFileSync(path, { encoding: "utf8" }));
};

/**
 * key 리스트 읽어오기
 * @param {string} path // __dirname + "/ABL생명_항목리스트.json"
 * @returns
 */
exports.readKeyList = function readKeyList(path, category) {
  let itemListFile = JSON.parse(fs.readFileSync(path, { encoding: "utf8" }));
  return itemListFile[category];
};

/**
 * JSON 파일 생성
 * @author Luna (syjang)
 * @param {string} path
 * @param {string} fileName
 * @param {object} resultJson
 */
exports.makeJsonFile = function makeJsonFile(FILE_PATH, fileName, resultJson) {
  fsPromises.writeFile(
    path.join(FILE_PATH, fileName),
    JSON.stringify(resultJson)
  );
};

/**
 * 영역추출모델 결과 가져오기
 * @author Luna (syjang)
 * @param {*} values
 * @param {*} filterTxt
 * @param {*} stType    default(절대좌표), keyword(키워드)
 * @param {*} resultTxt
 * @returns
 */
exports.setAreaSearchResult = function setAreaSearchResult(
  values,
  filterTxt,
  stType,
  resultTxt
) {
  let areaSearchResult = values?.filter(
    (value) => value?.ruleName === "AreaSearch"
  );

  areaSearchResult?.forEach((areaObj) => {
    areaObj?.data?.forEach((dataObj) => {
      for (let i = 0; i < Object.keys(dataObj)?.length; i++) {
        let key = Object.keys(dataObj)[i];

        if (filterTxt !== null)
          dataObj[key] = dataObj[key]?.filter(
            (o) => o?.userdescription === filterTxt
          );
        if (stType !== null)
          dataObj[key] = dataObj[key]?.filter((o) => o?.st_type === stType);
        if (resultTxt !== null)
          dataObj[key] = dataObj[key]?.filter(
            (o) => o?.value?.result === resultTxt
          );
      }
    });
  });

  return areaSearchResult;
};

/**
 * 결과 로그 출력
 * @author Luna (syjang)
 * @param {string} type
 * @param {object} values
 */
exports.printResultLog = function printResultLog(values) {
  Logger.log(
    "\n========================================================================================================================================================="
  );
  values?.sort((a, b) => {
    if (a.extc_itm_no != b.extc_itm_no) return a.extc_itm_no - b.extc_itm_no;
    else return a.extc_rst_seq - b.extc_rst_seq;
  });

  function upperCaseKeysInArray(arr) {
    return arr.map(obj =>
      Object.fromEntries(
        Object.entries(obj).map(([key, value]) => [
          key.toUpperCase(),
          value
        ])
      )
    );
  }

  function removeEmptyStringFields(arr) {
    return arr.map(obj =>
      Object.fromEntries(
        Object.entries(obj).filter(([_, value]) => value !== '')
      )
    );
  }

  values = upperCaseKeysInArray(values);
  console.table(removeEmptyStringFields(values), ["LVL_NO", "EXTC_ITM_NO", "EXTC_RST_SEQ", "HGRK_EXTC_ITM_NO"
    , "EXTC_RST_CONT08", "EXTC_ITM_TPVL", "EXTC_RST_CONT09", "EXTC_HGRK_ITNM", "IMG_EXTC_ITNM", "EXTC_RST_CONT01", "EXTC_RST_CONT10", "ACD_OGTDT", "EXTRTYN"]);

  Logger.log(
    "=========================================================================================================================================================\n"
  );
};

//-------------- [2026.01.12 추가] 진료비영수증 excel start -----------------
/**
 * @param {Array} extraData - 표 데이터 (lvl_no, extc_itm_tpvl 등 포함)
 * @param {Object} extractionResultData - 메타데이터(fileNm, category)
 */
exports.printResultExcelReceipt = async function printResultExcelReceipt(extraData, extractionResultData) {
    const fileNm = extractionResultData?.modelmapdata?.fileNm || "result";
    const category = extractionResultData?.modelmapdata?.category || "default";
    const excelfileName = `${fileNm}.xlsx`;
    const targetDir = path.join(excelPath, category);

    let wsData = Array.from({ length: 400 }, () => new Array(10).fill(""));
    let merges = [];
    
    // [중요] 에러 방지를 위해 변수들을 미리 선언 (Scope 문제 해결)
    let isSimpleHeader = false;
    let colMap = {};
    let currentRow = 18;

    const cleanVal = (val) => {
        if (!val || String(val).includes("[NO CONTENT FOUND]")) return "";
        let str = typeof val === 'object' ? JSON.stringify(val) : String(val);
        return str.length > 32000 ? str.substring(0, 32000) : str;
    };

    // 1. 계층 구조 필터링 (부모 삭제)
    const childHgrkIds = new Set(extraData.map(item => item.hgrk_extc_itm_no).filter(id => id));
    const filteredExtraData = extraData.filter(item => !childHgrkIds.has(item.extc_itm_no));

    // 2. 영역 분류
    const tableData = filteredExtraData.filter(item => item.extc_rst_cont10 === 'table-contents');
    const headerData = filteredExtraData.filter(item => item.extc_rst_cont10 !== 'table-contents');

    // 3. 상단 정보 배치
    let leftRowIdx = 0; let rightRowIdx = 1;
    wsData[0][6] = "진료비산정내용";
    headerData.forEach(item => {
        const key = item.img_extc_itnm || ""; const val = cleanVal(item.extc_rst_cont01);
        if (key.includes("총액") || key.includes("금액")) {
            wsData[rightRowIdx][6] = key; wsData[rightRowIdx][7] = val; rightRowIdx++;
        } else {
            wsData[leftRowIdx][0] = key; wsData[leftRowIdx][1] = val; leftRowIdx++;
        }
    });

    // 4. 동적 헤더 판별 및 컬럼 매핑
    const foundCont08 = new Set(tableData.map(d => d.extc_rst_cont08));
    
    // 조건 판별
    isSimpleHeader = (foundCont08.has("급여") || foundCont08.has("비급여")) && 
                     !foundCont08.has("본인부담금") && 
                     !foundCont08.has("공단부담금");

    const hasTotalNonPay = foundCont08.has("비급여") && !foundCont08.has("선택진료료");
    const headerR = 15;

    if (isSimpleHeader) {
        // [심플 모드]
        wsData[headerR][0] = "항목";
        wsData[headerR][3] = "급여";
        wsData[headerR][4] = "비급여";
        merges.push({ s: { r: headerR, c: 0 }, e: { r: headerR, c: 2 } });
        colMap = { '급여': 3, '비급여': 4 };
        currentRow = 16; // 데이터 시작점 조정
    } else {
        // [상세/혼합 모드]
        wsData[headerR][0] = "항목";
        wsData[headerR][3] = "급여"; 
        wsData[headerR+1][3] = "일부본인부담";
        wsData[headerR+2][3] = "본인부담금";
        wsData[headerR+2][4] = "공단부담금";
        wsData[headerR+1][5] = "전액본인부담";
        wsData[headerR][6] = "비급여";

        if (hasTotalNonPay) {
            wsData[headerR+1][6] = "비급여";
            merges.push({ s: { r: 16, c: 6 }, e: { r: 17, c: 7 } });
            colMap = { '비급여': 6 };
        } else {
            wsData[headerR+1][6] = "선택진료료";
            wsData[headerR+1][7] = "선택진료료이외";
            colMap = { '선택진료료': 6, '선택진료료이외': 7, '비급여': 7 };
        }

        colMap['본인부담금'] = 3; colMap['일부본인부담'] = 3;
        colMap['공단부담금'] = 4;
        colMap['전액본인부담금'] = 5; colMap['전액본인부담'] = 5;

        merges.push(
            { s: { r: 15, c: 0 }, e: { r: 17, c: 2 } },
            { s: { r: 15, c: 3 }, e: { r: 15, c: 5 } },
            { s: { r: 15, c: 6 }, e: { r: 15, c: 7 } },
            { s: { r: 16, c: 3 }, e: { r: 16, c: 4 } },
            { s: { r: 16, c: 5 }, e: { r: 17, c: 5 } }
        );
        currentRow = 18; // 데이터 시작점 조정
    }

    // 5. 본문 데이터 그룹화
    const grouped = new Map();
    const rowKeys = [];
    tableData.forEach(item => {
        const a = item.extc_itm_tpvl || ""; const b = item.extc_rst_cont09 || ""; const c = item.img_extc_itnm || "";
        const key = `${a}|${b}|${c}`;
        if (!grouped.has(key)) { grouped.set(key, { a, b, c, vals: {} }); rowKeys.push(key); }
        grouped.get(key).vals[item.extc_rst_cont08] = item.extc_rst_cont01;
    });

    // 6. 데이터 작성 및 가로 병합 (데이터 유실 방지 로직)
    const bodyStartRow = currentRow;
    const vMergeA = ["기본항목", "선택항목", "필수항목"];
    const vMergeB = ["입원료", "투약및조제료", "주사료", "투약조제료"];

    rowKeys.forEach(key => {
        const data = grouped.get(key);
        const r = currentRow;
        wsData[r][0] = data.a; wsData[r][1] = data.b; wsData[r][2] = data.c;

        // 가로 병합 시 값 유실 방지 (값을 왼쪽으로 이동)
        if (!data.a && !data.b) {
            wsData[r][0] = data.c; wsData[r][1] = ""; wsData[r][2] = "";
            merges.push({ s: { r, c: 0 }, e: { r, c: 2 } });
        } else if (!data.b) {
            wsData[r][1] = data.c; wsData[r][2] = "";
            merges.push({ s: { r, c: 1 }, e: { r, c: 2 } });
        }

        // 금액 데이터 매핑 부분 수정
        Object.entries(data.vals).forEach(([type, val]) => {
            const cIdx = colMap[type];
            if (cIdx !== undefined) {
                // 기존: 숫자가 아닌 것을 모두 제거 -> 수정: 숫자, 콤마, 마이너스(-) 기호만 남기고 제거
                let rawVal = String(val).trim();
                let numVal = rawVal.replace(/[^0-9.-]/g, ''); // 마이너스 기호(-)와 소수점(.) 허용

                if (numVal === "" || isNaN(numVal)) {
                    // 숫자가 아니면 텍스트로 삽입
                    wsData[r][cIdx] = cleanVal(val);
                } else {
                    // 숫자형으로 변환 (음수 기호 유지됨)
                    wsData[r][cIdx] = Number(numVal);
                }
            }
        });
        currentRow++;
    });

    // 7. 조건부 수직 병합
    const applyVMerge = (colIdx, targets) => {
        targets.forEach(target => {
            let startR = -1;
            for (let r = bodyStartRow; r < currentRow; r++) {
                if (wsData[r][colIdx] === target) { if (startR === -1) startR = r; }
                else { if (startR !== -1 && (r - 1) > startR) merges.push({ s: { r: startR, c: colIdx }, e: { r: r - 1, c: colIdx } }); startR = -1; }
            }
            if (startR !== -1 && (currentRow - 1) > startR) merges.push({ s: { r: startR, c: colIdx }, e: { r: currentRow - 1, c: colIdx } });
        });
    };
    applyVMerge(0, vMergeA);
    applyVMerge(1, vMergeB);

    // 8. 최종 병합 리스트 중복 제거 및 시트 생성
    const finalMerges = merges.filter((v, i, a) => 
        a.findIndex(t => t.s.r === v.s.r && t.s.c === v.s.c && t.e.r === v.e.r && t.e.c === v.e.c) === i
    );

    const ws = xlsx.utils.aoa_to_sheet(wsData);
    ws['!merges'] = finalMerges;
    const wb = xlsx.utils.book_new();
    xlsx.utils.book_append_sheet(wb, ws, fileNm);
    
    if (!fs.existsSync(targetDir)) fs.mkdirSync(targetDir, { recursive: true });
    xlsx.writeFile(wb, path.join(targetDir, excelfileName));
};

/**
 * @name clearDirectory
 * @description 특정 경로 내에 있는 폴더와 파일을 삭제한다.
 */
async function clearDirectory(targetDir) {
  const entries = fs.readdir(targetDir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(targetDir, entry.name);

    fs.rm(fullPath, {
      recursive: true,
      force: true
    });
  }
}

/**
 * @name removeDirectory
 * @description 특정 폴더를 삭제한다.
 */
async function removeDirectory(targetDir) {
  fs.rm(targetDir, {
    recursive: true,
    force: true
  });
}

/**
 * @name deleteFileSafe
 * @description 특정 파일을 삭제한다.
 */
async function deleteFileSafe(filePath) {
  fs.rm(filePath, { force: true });
}

//-------------- [2026.01.12 추가] 진료비영수증 excel end -----------------

function setExcelDataDozenChart(arrayOfArray, values, keyObj) {
  // 표데이터 출력
  let max_extrtSno = 0;

  let group = values
    ?.filter((value) => value?.extrtSno > 0)
    .reduce((acc, value) => {
      if (acc[value?.img_extc_rlp_itnm]) acc[value?.img_extc_rlp_itnm].push(value);
      else acc[value?.img_extc_rlp_itnm] = [value];

      if (max_extrtSno < value?.extrtSno) max_extrtSno = value?.extrtSno;

      return acc;
    }, {});

  for (let i = 0; i < Object.keys(group)?.length; i++) {
    arrayOfArray.push([]);

    let key = Object.keys(group)[i];
    let arr = group[Object.keys(group)[i]];

    let chartTitle = keyObj["표타이틀"];
    if (chartTitle.length < 1 && keyObj[`표타이틀_` + key]?.length > 0) {
      chartTitle = keyObj[`표타이틀_` + key];

      chartTitle = chartTitle.filter((title) => {
        let result = false;
        for (let i = 0; i < arr.length - 1; i++) {
          if (arr[i]?.extrtItmNm === title) {
            result = true;
            break;
          }
        }
        return result;
      });
    }

    // 표 이름
    chartTitle.unshift(key);
    chartTitle.push("추출여부");

    // 표 상단 제목
    arrayOfArray.push(chartTitle);

    let tmpArr = [];
    // [2025-04-11] 유효값 여부 확인 값
    // let lvlNum = 0;
    // let init = "Y";
    // let extrtArr = [];
    // let extrtNum = [];

    arr.forEach((value, idx) => {
      // 진료비영수증의 경우 진찰료, 입원료 등 기입
      if (chartTitle.indexOf(value?.extrtItmNm) < 0) {
        if (value?.extrtSno === 1) tmpArr.push(value?.extrtItmNm);

        tmpArr.push(value?.extrtCntnt);

        if (value?.extrtSno === max_extrtSno) {
          tmpArr.push(value?.extrtYn);

          arrayOfArray.push(tmpArr);

          tmpArr = [];
        }
      } else {
        // 진료비세부내역서와 같은 유형의 표 데이터는 레벨번호 기입
        if (value?.extrtSno === 1) {
          tmpArr.push(value?.extrtLvlNo);

          // [2025-04-11] 유효값 여부 확인용
          // if (lvlNum !== 0) init = "N";
          lvlNum = value?.extrtLvlNo;
        }

        // [2025-04-11] 유효값 여부 확인용
        // if (lvlNum === value?.extrtLvlNo) {
        //   // [2025-04-11] 첫 line일 경우 extrtNum push 필요
        //   if (init === "Y") {
        //     // [2025-04-11] 유효값이 아닐 경우는 1 push
        //     if (value?.extrtCntnt?.length === 0 && value?.extrtYn === "N") {
        //       extrtNum.push(1);
        //       // [2025-04-11] 유효값일 경우에는 0 push
        //     } else {
        //       extrtNum.push(0);
        //     }

        //     // 두번째 line 부터는 해당 순서에 반영
        //   } else {
        //     // [2025-04-11] 유효값이 아닐 경우는 1 더하기
        //     if (value?.extrtCntnt?.length === 0 && value?.extrtYn === "N") {
        //       extrtNum[value?.extrtSno - 1] = extrtNum[value?.extrtSno - 1] + 1;
        //     }
        //   }
        // }

        tmpArr.push(value?.extrtCntnt);
        if (value?.extrtSno === chartTitle.length - 2) {
          tmpArr.push(value?.extrtYn);

          // arrayOfArray.push(tmpArr);
          // [2025-04-11] 유효값 반영
          // extrtArr.push(tmpArr);

          tmpArr = [];
          // [2024.10.28.]진료비세부내역서 push
        } else if (value?.extrtSno === max_extrtSno) {
          tmpArr.push(value?.extrtYn);

          arrayOfArray.push(tmpArr);
          // [2025-04-11] 유효값 반영
          // extrtArr.push(tmpArr);

          tmpArr = [];
        }
      }
    });

    // [2025-04-11] 레벨번호, 추출여부 반영
    // extrtNum.unshift(0);
    // extrtNum.push(0);

    // let deleteNum = [];
    // if (extrtNum?.length > 2 && extrtArr?.length > 0) {
    //   // 유효값이 아닌 row 추출
    //   extrtNum?.forEach((extrt, i) => {
    //     if (extrt === extrtArr?.length) deleteNum.push(i);
    //   });
    // }

    // '표타이틀'에서 유효값만 남기기
    let filteredTitle = chartTitle.filter((_, idx) => !deleteNum.includes(idx));
    // extrtArr에서 유효값만 남기기
    let cleanedArr = extrtArr.map((row) =>
      row.filter((_, idx) => !deleteNum.includes(idx))
    );

    if (filteredTitle?.length > 0 && cleanedArr?.length > 0) {
      // 기존 '표타이틀' 제거
      arrayOfArray.pop();

      arrayOfArray.push(filteredTitle);
      arrayOfArray.push(...cleanedArr);
    }

    if (i === Object.keys(group)?.length - 1) arrayOfArray.push([]);
  }
}

function setExcelDataSingleChart(arrayOfArray, values, keyObj) {
  arrayOfArray.push([]);

  // 표데이터 출력
  let max_extrtSno = 0;

  let group = values
    ?.filter((value) => value?.extrtSno > 0)
    .reduce((acc, value) => {
      if (acc[value?.extrtItmNm]) acc[value?.extrtItmNm].push(value);
      else acc[value?.extrtItmNm] = [value];

      if (max_extrtSno < value?.extrtSno) max_extrtSno = value?.extrtSno;

      return acc;
    }, {});
  let chartTitle = keyObj["표타이틀"];
  chartTitle.unshift("");
  chartTitle.push("추출여부");

  arrayOfArray.push(chartTitle);

  for (let i = 0; i < Object.keys(group)?.length; i++) {
    let key = Object.keys(group)[i];
    let arr = group[Object.keys(group)[i]];

    let tmpArr = [];
    // array push 여부 판별 값
    let pushNum = 1;
    arr.forEach((value) => {
      if (value?.extrtSno === 1) tmpArr.push(value?.extrtItmNm);
      else {
        // [2025-04-11] 공백이면서 추출여부가 'N'인 값은 포함하지 않음
        if (value?.extrtCntnt === "" && value?.extrtYn === "N") pushNum++;
      }

      tmpArr.push(value?.extrtCntnt);

      if (value?.extrtSno === max_extrtSno) {
        tmpArr.push(value?.extrtYn);

        // [2025-04-11] 해당 항목 값 중 유효값이 있을 때만 push
        if (pushNum !== max_extrtSno) arrayOfArray.push(tmpArr);

        tmpArr = [];
        pushNum = 1;
      }
    });
  }
}

/**
 * extractionResultData 에서 arrtcd 가져오기
 * @author Luna (syjang)
 * @param {Array} modelmap extractionResultData?.modelmapdata
 * @returns {Array} arrtcd return
 */
exports.getArrtcd = function getArrtcd(modelmap) {
  let contents = modelmap?.contents;
  let tcd = contents?.filter((v) => v?.key === "cell");
  let arrtcd = tcd[0]?.value || [];

  return arrtcd;
};

/**
 * extractionResultData 에서 arrmodel 가져오기
 * @author Luna (syjang)
 * @param {Array} modelmap extractionResultData?.modelextract
 * @returns {Array} arrtcd return
 */
exports.getArrmodel = function getArrmodel(modelmap) {
  let contents = modelmap?.contents;
  let tcd = contents?.filter((v) => v?.key === "modelextract");
  let arrmodel = tcd[0]?.value || [];

  return arrmodel;
};

/**
 * arrtcd 중 name 이 keyword, mergetext 와 같은 그룹 리스트 가져오기
 * @author Luna (syjang)
 * @param {Array} arrtcd 기본 arrtcd ( modelmap?.contents 에서 key 가 cell 인 것들의 value )
 * @param {string} name 추출하고자 하는 항목과 동일한 group 에 있는 name
 * @returns {Array} arrtcd keyword, mergetext 에 name 이 포함되는 것의 groupidx 를 가져와 같은 그룹에 있는 항목들의 리스트를 return
 */
exports.getArrtcdValue = function getArrtcdValue(arrtcd, name) {
  let tcd = arrtcd?.filter(
    (fv) =>
      fv?.keyword === name ||
      fv?.mergetext === name ||
      fv?.keyword?.includes(name) ||
      fv?.mergetext?.includes(name)
  );
  let groupidx = tcd[0]?.groupidx || null;

  return arrtcd?.filter((fv) => fv?.groupidx === groupidx);
};

/**
 * arrtcd 중 index 기준으로 가져오기
 * @author Luna (syjang)
 * @param {Array} arrtcd 기본 arrtcd ( modelmap?.contents 에서 key 가 cell 인 것들의 value )
 * @param {string} index 추출하고자 하는 항목 index
 * @returns {Array} arrtcd keyword, mergetext 에 name 이 포함되는 것의 groupidx 를 가져와 같은 그룹에 있는 항목들의 리스트를 return
 */
exports.getArrtcdIdxValue = function getArrtcdIdxValue(arrtcd, index) {
  return arrtcd?.filter((fv) => fv?.index === index);
};

/**
 * arrtcd 를 활용하여 grouidx 가져오기
 * @author Luna (syjang)
 * @param {Array} arrtcd 기본 arrtcd ( modelmap?.contents 에서 key 가 cell 인 것들의 value )
 * @param {string} name 추출하고자 하는 항목과 동일한 group 에 있는 name
 * @returns {number} groupidx keyword, mergetext 에 name 이 포함되는 것의 groupidx를 return
 */
exports.getArrtcdGroupIdx = function getArrtcdGroupIdx(arrtcd, name) {
  let tcd = arrtcd?.filter(
    (fv) =>
      fv?.keyword === name ||
      fv?.mergetext === name ||
      fv?.keyword?.includes(name) ||
      fv?.mergetext?.includes(name)
  );
  let groupidx = tcd[0]?.groupidx || null;

  return groupidx;
};

/**
 * arrtcd 를 활용하여 grouidx 가져오기 - detectedIndex
 * @author Luna (syjang)
 * @param {Array} arrtcd 기본 arrtcd ( modelmap?.contents 에서 key 가 cell 인 것들의 value )
 * @param {string} detectedIndex 추출하고자 하는 항목과 동일한 group 에 있는 detectedIndex
 * @returns {number} groupidx keyword, mergetext 에 name 이 포함되는 것의 groupidx를 return
 */
exports.getArrtcdDetIdx = function getArrtcdDetIdx(arrtcd, detectedIndex) {
  let tcd = arrtcd?.filter(
    (fv) => fv?.index === detectedIndex || fv?.index === detectedIndex
  );
  let groupidx = tcd[0]?.groupidx || null;

  return groupidx;
};

/**
 * arrtcd 중 groupidx 와 동일한 그룹 리스트 가져오기
 * @author Luna (syjang)
 * @param {Array} arrtcd 기본 arrtcd ( modelmap?.contents 에서 key 가 cell 인 것들의 value )
 * @param {number} groupidx 추출하고자 하는 groupidx
 * @returns {Array} arrtcd 넘겨받은 groupidx 와 같은 그룹에 있는 항목들의 리스트를 return
 */
exports.getArrtcdGroupValue = function getArrtcdGroupValue(arrtcd, groupidx) {
  return arrtcd?.filter((fv) => fv?.groupidx === groupidx);
};

/**
 * arrtcd 값에 있는 모든 mergetext 를 가져와서 string 형태로 return
 * @author Luna (syjang)
 * @param {Array} arrtcd 가공한 arrtcd ( 추출하고자 하는 grouidx 를 기준으로 getArrtcdValue 혹은 getArrtcdGroupValue 를 호출한 결과 )
 * @retruns {string} label 파라미터로 받은 arrtcd 의 모든 mergetext 값을 string 형태로 merge 하여 return
 */
exports.setArrtcdLabel = function setArrtcdLabel(arrtcd) {
  let label = "";

  arrtcd?.forEach((tcd, idx) => {
    // if(idx !== 0) label += ' ';

    //mergetext 로 할시 등록된 대표어가 아닌 동의어들로도 키워드가 만들어지기 때문에 대표어로 바꿈 -20241025
    // label += tcd.mergetext;
    label += tcd.keyword;
  });

  return label;
};

/**
 * arrtcd 의 children, topitems, leftitems, rightitems, bottomitems return
 * @author Luna (syjang)
 * @param {Array} arrtcd 기본 arrtcd ( modelmap?.contents 에서 key 가 cell 인 것들의 value )
 * @param {string} name 기준이 되는 name
 * @param {number} index 기준이 되는 index (default = null)
 * @param {string} type children, top, left, right, bottom 중 입력
 * @returns {Array} arrtcd 의 children, topitems, leftitems, rightitems, bottomitems return
 */
exports.getArrtcdLowArr = function getArrtcdLowArr(
  arrtcd,
  name = null,
  index = null,
  type
) {
  let tcd = arrtcd?.filter(
    (fv) =>
      fv?.keyword === name ||
      fv?.mergetext === name ||
      fv?.keyword?.includes(name) ||
      fv?.mergetext?.includes(name)
  );
  if (name !== null)
    tcd = arrtcd?.filter(
      (fv) =>
        fv?.keyword === name ||
        fv?.mergetext === name ||
        fv?.keyword?.includes(name) ||
        fv?.mergetext?.includes(name)
    );
  if (index !== null) tcd = arrtcd?.filter((fv) => fv?.index === index);

  switch (type) {
    case "children":
      return tcd[0]?.children;
    case "top":
      return tcd[0]?.relation?.topitems;
    case "left":
      return tcd[0]?.relation?.leftitems;
    case "right":
      return tcd[0]?.relation?.rightitems;
    case "bottom":
      return tcd[0]?.relation?.bottomitems;
    default:
      return tcd;
  }

  return tcd;
};

/**
 * arrtcd
 * @author Luna (syjang)
 * @param {Array} arrtcd
 * @param {Array} indexes
 * @param {string} name
 * @param {string} direction
 * @returns {string} result
 */
exports.getTxtMerge = function getTxtMerge(arrtcd, indexes, name, direction) {
  let result = "";

  let lastIdx = indexes[indexes.length - 1];
  while (true) {
    let tmpArrtcd = this.getArrtcdLowArr(arrtcd, name, lastIdx, direction);
    lastIdx = tmpArrtcd[0]?.index;

    if (typeof lastIdx === "undefined") break;
    result += arrtcd[lastIdx]?.mergetext;
  }

  return result;
};

/**
 * cell 간 width 의 평균 측정
 * @author Luna (syjang)
 * @param {Array} data
 * @returns {number} widthAvg
 */
exports.getCellWidthAvg = function getCellWidthAvg(data) {
  let widthAvg = 0;
  let dist = 0;

  // Page1.values[0].data[0].values.length > 1 인 경우 cell 간 width의 평균 측정
  let widthSum = 0;
  data?.values?.forEach((v) => {
    if (typeof v?.ocrInfo !== "undefined") {
      let coord = v?.ocrInfo[0]?.coordinates;
      let label = v?.ocrInfo[0]?.label;

      if (
        typeof coord !== "undefined" &&
        typeof label !== "undefined" &&
        label?.length > 0
      )
        widthSum += ((coord[4] - coord[0] - 4) / label?.length) * 0.8;
    }
  });
  widthAvg = widthSum / data?.values?.length;

  return widthAvg;
};

/**
 * 오인식 처리를 위한 로직 - 현재 cell 우측에 있는 항목 간 거리 비교
 * @author Luna (syjang)
 * @param {boolean} distChkPoint
 * @param {Array} arrtcd
 * @param {string} label
 * @param {number} index
 * @param {string} direction children, top, left, right, bottom 중 입력 (default=right)
 * @returns {boolean} distChkPoint
 */
exports.getDistChkPoint = function getDistChkPoint(
  distChkPoint,
  widthAvg,
  arrtcd,
  label,
  index,
  direction = "right"
) {
  let dist = 0;
  let tmpDistArr = this.getArrtcdLowArr(arrtcd, label, index, direction);

  if (tmpDistArr) dist = tmpDistArr[0]?.dist;
  if (dist > widthAvg + 4) distChkPoint = true;

  return distChkPoint;
};

/**
 * 취소선이 적용되지 않은 텍스트를 리스트 형태로 return
 * @author Luna (syjang)
 * @param {Array} arrtcd 기본 arrtcd ( modelmap?.contents 에서 key 가 cell 인 것들의 value )
 * @param {Array} groupValue (default : [])
 * @param {string} name 추출하고자 하는 name
 * @param {string} mainKey 추출하고자 하는 key
 * @param {string} subKey 확인을 중단할 key
 * @returns {Array} groupValue
 */
exports.getNonCancelTxt = function getNonCancelTxt(
  arrtcd,
  groupValue = [],
  name,
  mainKey,
  subKey
) {
  if (groupValue?.length < 1) {
    groupValue = this.getArrtcdValue(arrtcd, name);
    groupValue = groupValue?.filter((gv) => gv?.mergetext !== "");
  }

  let chkPoint = false;
  let result = [];

  for (let g = 0; g < groupValue?.length; g++) {
    if (groupValue[g]?.iskeyword === true && groupValue[g]?.keyword === mainKey)
      chkPoint = true;
    else if (
      groupValue[g]?.iskeyword === true &&
      groupValue[g]?.keyword === subKey
    )
      chkPoint = false;
    else if (groupValue[g]?.mergetext?.includes(subKey)) chkPoint = false;

    if (!chkPoint || groupValue[g]?.iskeyword) continue;

    let childArr = groupValue[g]?.children?.filter(
      (child) => !child?.cancelline
    );
    if (groupValue[g]?.iskeyword === false && childArr?.length > 0) {
      result.push(groupValue[g]?.mergetext);
    }
  }

  return result;
};

/**
 * arrtcd 를 활용하여 생성된 전체 Group Index 추출(중복제거)
 * @author Joseph (jhchae)
 * @param {Array} arrtcd coordinate merge를 arrtcd의 요소들
 * @returns {Array} Group Index 목록
 */
exports.getAllGroupIdx = function getAllGroupIdx(arrtcd) {
  let getAllGroupIdx = arrtcd?.map((v) => v?.groupidx);

  getAllGroupIdx = [...new Set(getAllGroupIdx)];
  return getAllGroupIdx;
};

/**
 * arrtcd 를 활용하여 요소들의 coordinate 계산하기
 * @author Joseph (jhchae)
 * @param {Array} arrtcd coordinate merge를 arrtcd의 요소들
 * @returns {Array} coordinate merge를 한 결과인 coordinates 좌표 값들
 */
exports.getCoordinateMerge = function getCoordinateMerge(arrtcd) {
  let defaultCoordinates = [];
  let topLeftPoints = [];
  let bottomLeftPoints = [];
  let bottomRightPoints = [];
  let topRightPoints = [];

  if (items.length === 0) return defaultCoordinates;
  if (items.length === 1) {
    let element = items[0];
    return element?.coord || defaultCoordinates;
  }

  // merge coordinates
  arrtcd.forEach((element) => {
    let coordinates = element?.coord;
    let topLeftPoint = [coordinates[0], coordinates[1]];
    let bottomLeftPoint = [coordinates[2], coordinates[3]];
    let bottomRightPoint = [coordinates[4], coordinates[5]];
    let topRightPoint = [coordinates[6], coordinates[7]];

    topLeftPoints.push(topLeftPoint);
    bottomLeftPoints.push(bottomLeftPoint);
    bottomRightPoints.push(bottomRightPoint);
    topRightPoints.push(topRightPoint);
  });

  let topLeftMinX = funcMinX(topLeftPoints);
  let topLeftMinY = funcMinY(topLeftPoints);
  let bottomLeftMinX = funcMinX(bottomLeftPoints);
  let bottomLeftMaxY = funcMaxY(bottomLeftPoints);
  let bottomRightMaxX = funcMaxX(bottomRightPoints);
  let bottomRightMaxY = funcMaxY(bottomRightPoints);
  let topRightMaxX = funcMaxX(topRightPoints);
  let topRightMinY = funcMinY(topRightPoints);

  let mergedCoordinates = [
    topLeftMinX,
    topLeftMinY,
    bottomLeftMinX,
    bottomLeftMaxY,
    bottomRightMaxX,
    bottomRightMaxY,
    topRightMaxX,
    topRightMinY,
  ];

  return mergedCoordinates;
};

const funcMinX = function (points) {
  let minX = Math.min.apply(
    null,
    points.map((v) => v[0])
  );
  return minX;
};
const funcMinY = function (points) {
  let minY = Math.min.apply(
    null,
    points.map((v) => v[1])
  );
  return minY;
};
const funcMaxX = function (points) {
  let maxX = Math.max.apply(
    null,
    points.map((v) => v[0])
  );
  return maxX;
};
const funcMaxY = function (points) {
  let maxY = Math.max.apply(
    null,
    points.map((v) => v[1])
  );
  return maxY;
};

exports.getBytes = function getBytes(contents) {
  let str;
  let cnt = 0;
  let len = contents?.length;

  for (let i = 0; i < len; i++) {
    str = contents.charAt(i);

    if (escape(str).length > 4) cnt += 2;
    else cnt++;
  }

  return cnt;
};

exports.saveValuesCountToExcel = async function saveValuesCountToExcel(
  category,
  fileNm,
  valuesCount
) {
  try {
    // 엑셀 데이터 준비
    let data = [[valuesCount]];

    // 엑셀 워크북 및 워크시트 생성
    let workbook = xlsx.utils.book_new();
    let worksheet = xlsx.utils.aoa_to_sheet(data);

    xlsx.utils.book_append_sheet(workbook, worksheet, "Count");

    // 디렉토리 확인 및 생성
    const categoryPath = path.join(valuePath, category);
    if (!fs.existsSync(valuePath)) await fsPromises.mkdir(valuePath);
    if (!fs.existsSync(categoryPath)) await fsPromises.mkdir(categoryPath);

    // 파일 저장
    let filePath = path.join(categoryPath, `${fileNm}.xlsx`);
    xlsx.writeFile(workbook, filePath);

  } catch (error) {
    Logger.error("⚠️ Error saving values count to Excel:", JSON.stringify({
      message: error.message,
      stack: error.stack.split("\n")
    }, null, 2));
  }
};
