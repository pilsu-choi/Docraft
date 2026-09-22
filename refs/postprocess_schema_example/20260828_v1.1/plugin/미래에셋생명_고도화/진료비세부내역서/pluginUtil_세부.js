// const {Logger}              = require('common/logger');
const {Logger}              = require('/usr/src/app/dist/apps/extn/libs/common/src/');

const path = require('path');
const fs = require('fs');
const fsPromises = require('fs/promises');

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
}

/**
 * key 리스트 읽어오기
 * @param {string} path // __dirname + "/ABL생명_항목리스트.json"
 * @returns 
 */
exports.readKeyList = function readKeyList(path, category) {
  let itemListFile = JSON.parse(fs.readFileSync(path, { encoding: "utf8" }));
  return itemListFile[category];
}

/**
 * JSON 파일 생성
 * @author Luna (syjang)
 * @param {string} path
 * @param {string} fileName
 * @param {object} resultJson
 */
exports.makeJsonFile = function makeJsonFile(FILE_PATH, fileName, resultJson) {
  fsPromises.writeFile(path.join(FILE_PATH, fileName), JSON.stringify(resultJson));
}

/**
 * 영역추출모델 결과 가져오기
 * @author Luna (syjang)
 * @param {*} values 
 * @param {*} filterTxt 
 * @param {*} stType    default(절대좌표), keyword(키워드)
 * @param {*} resultTxt
 * @returns 
 */
exports.setAreaSearchResult = function setAreaSearchResult(values, filterTxt, stType, resultTxt) {
  let areaSearchResult = values?.filter((value) => value?.ruleName === 'AreaSearch');

  areaSearchResult?.forEach((areaObj) => {
    areaObj?.data?.forEach((dataObj) => {
      for (let i = 0; i < Object.keys(dataObj)?.length; i++) {
        let key = Object.keys(dataObj)[i];

        if (filterTxt !== null) dataObj[key] = dataObj[key]?.filter((o) => o?.userdescription === filterTxt);
        if (stType !== null) dataObj[key] = dataObj[key]?.filter((o) => o?.st_type === stType);
        if (resultTxt !== null) dataObj[key] = dataObj[key]?.filter((o) => o?.value?.result === resultTxt);
      }
    });
  });

  return areaSearchResult;
}

/**
 * 결과 로그 출력
 * @author Luna (syjang)
 * @param {string} type 
 * @param {object} values 
 */
exports.printResultLog = function printResultLog(type, values) {
  // Logger.log('\n=========================================================================================================================================================');
  // values?.sort((a, b) => {
  //   if (a.lvl_no != b.lvl_no) return a.lvl_no - b.lvl_no;
  //   else return a.extc_rst_seq - b.extc_rst_seq;
  // });
  console.table(
    values.map((v, i) => ({
      img_extc_itnm: v.img_extc_itnm,
      lvl_no: v.lvl_no,
      extc_itm_no: v.extc_itm_no,
      extc_rst_seq: v.extc_rst_seq,
      hgrk_extc_itm_no: v.hgrk_extc_itm_no,
      extc_itm_tpvl: v.extc_itm_tpvl,
      extc_rst_cont01: v.extc_rst_cont01,
      extc_rst_cont09: v.extc_rst_cont09,
      extc_rst_cont10: v.extc_rst_cont10,
      self_rlbtr_vl: v.self_rlbtr_vl,
      extc_rst_img_crdn_vl : v.extc_rst_img_crdn_vl,
      acd_ogtdt: v.acd_ogtdt
      // extc_rst_img_crdn_vl: v.extc_rst_img_crdn_vl
    }))
  )
  // if(!type.includes('simple')) Logger.log('INDEX\t\t추출항목명\t\t추출레벨번호\t\t추출항목순서\t\textc_rst_seq\t\thgrk\t\ttpvl\t\tcont01\t\tcont09\t\tcont10');
  // else Logger.log('INDEX\t\t추출여부\t차트이름\t\t\t추출항목명\t\t\t추출내용');

  // values?.forEach((value, i) => {
  //   let tab = '';
  //   if (this.getBytes(value.img_extc_itnm) < 7) tab = '\t\t\t\t';
  //   else if (this.getBytes(value.img_extc_itnm) < 16) tab = '\t\t\t\t';
  //   else tab = '\t';

  //   if((type.includes('short') && value.extc_rst_seq < 1) || !type.includes('short')) {
  //     if(!type.includes('simple')) Logger.log((i+1) + '\t\t' + value.img_extc_itnm + '\t\t\t' + value.lvl_no + '\t\t' + value.extc_itm_no + '\t\t' + value.extc_res_seq + '\t\t' + value.extc_itm_tpvl + '\t\t' + value.extc_rst_cont01 + tab + value.extc_rst_cont09 + '\t\t\t' + value.extc_rst_cont10);
  //     else Logger.log(i + '\t\t' + value.extrtYn + '\t\t' + value.chartNm + (value.chartNm === null ? '\t\t\t\t' : '\t\t') + value.img_extc_itnm + tab + value.extc_rst_cont01);
  //   }
  // });

  // Logger.log('=========================================================================================================================================================\n');
}

/**
 * 결과 로그 출력 엑셀 변환 용
 * @author Luna (syjang)
 * @param {string} type 
 * @param {object} values 
 */

exports.printResultLogExcel = function printResultLogExcel(type, values, extractionResultData, keyObj) {

  // [2025-04-10] 추출여부 'Y'인 항목만 남기기
  // values = values?.filter((value) => value?.extrtYn === 'Y');

  Logger.log('\n=========================================================================================================================================================');

  if (type.includes("log")) {
    values?.sort((a, b) => {
      if (a.lvl_no != b.lvl_no) return a.lvl_no - b.lvl_no;
      else return a.extc_rst_seq - b.extc_rst_seq;
    });

    Logger.log('INDEX|추출ID|추출레벨번호|추출일련번호|추출여부|본인신뢰도값|추출항목명|추출내용');
    values?.forEach((value, i) => {
      // Logger.log("1111111111111",value)
      if ((type.includes('short') && value.extc_rst_seq < 1) || !type.includes('short')) {
        Logger.log((i + 1) + '|' + value.extc_itm_no + '|' + value.lvl_no + '|' + value.extc_rst_seq + '|' + value.extrtYn + '|' + value.self_ribtr_vl + '|' + value.img_extc_itnm + '|' + value.extc_rst_cont01);
      }
    });
  }

  // 엑셀 데이터 셋팅
  if (type.includes("excel")) {

    let arrayOfArray = [["레벨번호", "추출항목명", "추출내용", "추출여부"]];
    // let arrayOfArray = [["레벨번호","추출항목명","추출내용"]];

    // 표데이터가 아닌 값 먼저 출력
    values?.filter((value) => (value?.extc_rst_seq < 1) && (value?.chartNm != "계"))
      .forEach((value) => {
        // [2025-04-13] 공백이면서 추출여부가 'N'인 값은 포함하지 않음
        if (!(value?.extc_rst_cont01?.length == 0 && value?.extrtYn == "N")) {
          arrayOfArray.push([value?.lvl_no, value?.img_extc_itnm, value?.extc_rst_cont01, value?.extrtYn]);
        }
        // arrayOfArray.push([value?.lvl_no, value?.img_extc_itnm, value?.extc_rst_cont01, value?.extrtYn]);
      });
    let salaryItems = []; // "일부본인부담금"을 구분하기 위한 카운터
    let seen = new Set();
    // Logger.log("11111",values)
    values?.filter((value) => (value?.extc_rst_seq < 1) && (value?.chartNm == "계"))
      .forEach((value) => {
        let newExtractionItem = `${value?.chartNm}_${value?.img_extc_itnm}`;
        // "일부본인부담금"이면 따로 저장 후 나중에 처리
        if (value?.img_extc_itnm === "일부본인부담금") {
          salaryItems.push({ lvl_no: value?.lvl_no, name: newExtractionItem, content: value?.extc_rst_cont01, result: value?.extrtYn, chart: value?.chartNm });
          // salaryItems.push({ lvl_no:value?.lvl_no, name: newExtractionItem, content: value?.extc_rst_cont01, chart: value?.chartNm });
        } else {
          let uniqueKey = `${value?.lvl_no}|${newExtractionItem}|${value?.extc_rst_cont01}|${value?.extrtYn}`;
          // let uniqueKey = `${value?.lvl_no}|${newExtractionItem}|${value?.extc_rst_cont01}`;
          if (!seen.has(uniqueKey)) {
            seen.add(uniqueKey);
            arrayOfArray.push([value?.lvl_no, newExtractionItem, value?.extc_rst_cont01, value?.extrtYn]);
            // arrayOfArray.push([value?.lvl_no,newExtractionItem, value?.extc_rst_cont01]);
          }
        }
      });
    salaryItems.forEach((item, index) => {
      let newName = index % 2 === 0 ? `${item.chart}_일부본인부담금_급여` : `${item.chart}_일부본인부담금_비급여`;
      let uniqueKey = `${newName}|${item.content}|${item.result}`;
      if (!seen.has(uniqueKey)) {
        seen.add(uniqueKey);
        arrayOfArray.push([item.lvl_no, newName, item.content, item.result]);
      }
    });

    let sortedArray = [arrayOfArray[0], ...arrayOfArray.slice(1).sort((a, b) => a[0] - b[0])];
    if (keyObj['표추출항목'] && keyObj['표추출항목']?.length > 0) {
      // 진료비영수증
      setExcelDataSingleChart(sortedArray, values, keyObj);
    } else {
      // 표가 여러 개인 경우
      setExcelDataDozenChart(sortedArray, values, keyObj);
    }

    // [2025-04-10] 레벨번호, 추출여부 제거
    // sortedArray?.forEach((sa) => {
    //   if(sa?.length > 0) {
    //     if(typeof(sa[0]) === "number") sa.shift();
    //     else if(sa[0]?.includes("레벨번호") || sa[0]?.includes("표데이터")) sa.shift();
    //     sa.pop();
    //   }
    // });

    // 엑셀 생성
    let fileNm = extractionResultData.modelmapdata.fileNm;
    let category = extractionResultData.modelmapdata.category;

    let splitBook = xlsx.utils.book_new();
    let excelfileName = fileNm + ".xlsx";


    // let document = xlsx.utils.aoa_to_sheet(sortedArray);

    // document["!cols"]     = [{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100}];

    // xlsx.utils.book_append_sheet(splitBook, document, "결과");

    const headers = [
      "img_extc_itnm",
      "extc_rst_cont01",
      "extc_rst_cont09",
      "extc_rst_cont10",
      "lvl_no",
      "extc_itm_no",
      "extc_rst_seq",
      "hgrk_extc_itm_no",
      "extc_itm_tpvl",
      "self_ribtr_vl",
      "chartNm",
      "acd_ogtdt"
    ];

    let document = xlsx.utils.json_to_sheet(values, {
      header: headers,
      skipHeader: false
    });

    document["!cols"] = headers.map(() => ({ wpx: 160 }));
    xlsx.utils.book_append_sheet(splitBook, document, "결과")


    //================================================== 0203 검증 소스 추가 start ================================================
    try {
      const extraDataAll = getAllextraDataWithPage(extractionResultData);
      // Logger.log("@@@@@@@@@@@@@@@@@",extraDataAll)
      if (extraDataAll.length > 0) {
        const { allRows, failRows } = validateExtraData(extraDataAll);

        const appendRows = [
          [],
          ["[검증결과]"],
          ...allRows
        ]
        xlsx.utils.sheet_add_aoa(document, appendRows, { origin: -1 });
      }
    } catch (e) {
      Logger.error("validation error:", JSON.stringify({
        message: error.message,
        stack: error.stack.split("\n")
      }, null, 2));
    }

    //================================================== 0203 검증 소스 추가 end ================================================

    if (!fs.existsSync(excelPath)) fsPromises.mkdir(excelPath);
    if (!fs.existsSync(path.join(excelPath, category))) fsPromises.mkdir(path.join(excelPath, category));

    xlsx.writeFile(splitBook, path.join(excelPath, category, excelfileName));
  }

  Logger.log('=========================================================================================================================================================\n');
}

//================================================================================= setExcelDataDozenChart 변경 0121
function setExcelDataDozenChart(arrayOfArray, values, keyObj) {

  let max_extrtSno = 0;
  const group = values?.filter(v => v?.extc_rst_seq > 0)
    .reduce((acc, v) => {
      if (acc[v?.chartNm]) acc[v?.chartNm].push(v);
      else acc[v?.chartNm] = [v];

      if (max_extrtSno < v?.extc_rst_seq) max_extrtSno = v?.extc_rst_seq;
      return acc;
    }, {});


  //hadder기준으로 row 배열 생성 (빈값은 "" 유지)
  const buildRow = (header, rowObj) => header.map(h => rowObj?.[h] ?? "");

  const chartKeys = Object.keys(group || {});
  for (let i = 0; i < chartKeys.length; i++) {
    arrayOfArray.push([]);

    const key = chartKeys[i];
    const arr = group[key] || [];

    //표 타이틀(기존로직 유지)
    let chartTitle = Array.isArray(keyObj["표타이틀"]) ? [...keyObj["표타이틀"]] : [];

    if (!chartTitle.includes("추출여부")) chartTitle.push("추출여부");

    if (key === "표데이터") {
      const mustCols = ["본인부담", "공단부담", "전액본인부담", "비급여"];
      mustCols.forEach(c => {
        if (!chartTitle.includes(c)) chartTitle.push(c)
      });
    }
    //표 이름
    chartTitle.unshift(key);
    chartTitle.push("추출여부");

    //표 상단 제목
    arrayOfArray.push(chartTitle);

    //밀림 방지
    //row를 push로 만들지 않고 Object로 만든 다음 header로 변환
    const rowMap = new Map();
    const skipRowKeys = new Set();
    const getRowKey = (v) => String(v?.extc_itm_no ?? "");

    const normalizeColName = (key, colName) => {
      const k = String(key ?? "").trim();
      const c = String(colName ?? "").trim();

      if (k !== "표데이터") return c;

      const t = c.replace(/\s+/g, "").replace(/-/g, "");
      if (t.includes("공단") && !t.includes("소계") && !t.includes("합계")) return "공단부담";
      if (t.includes("전액") && t.includes("본인부담") && !t.includes("소계") && !t.includes("합계")) return "전액본인부담";
      if (t.includes("본인부담") && !t.includes("소계") && !t.includes("합계")) return "본인부담";
      if (t.includes("비급여") && !t.includes("소계") && !t.includes("합계")) return "비급여";
      if (t.includes("EDI코드")) return "코드";

      return c;
    }

    arr.forEach(v => {
      const rowKey = getRowKey(v);
      if (!rowKey) return;

      if (!rowMap.has(rowKey)) rowMap.set(rowKey, {});
      const rowObj = rowMap.get(rowKey);

      // if (v?.img_extc_itnm === "항목") {
      //   const itemVal = String(v?.extc_rst_cont01 ?? "").trim();
      //   if(itemVal.includes("소계") || itemVal.includes("합계")) {
      //     skipRowKeys.add(rowKey);
      //     return;
      //   }
      // }
      if (skipRowKeys.has(rowKey)) return;
      rowObj[key] = v?.extc_itm_no ?? "";

      const rawColName = v?.img_extc_itnm
      const colName = rawColName ? normalizeColName(key, rawColName) : "";
      if (colName) rowObj[colName] = v?.extc_rst_cont01 ?? "";

      rowObj["추출여부"] = v?.extrtYn ?? rowObj["추출여부"] ?? "";

      // Logger.log("rowKey", getRowKey(v), "extc_itm_no", v.extc_itm_no, "lvl_no", v.lvl_no, "col", v.img_extc_itnm, "val", v.extc_rst_cont01 )
      // if (key === "표데이터") {
      //   Logger.log("COL", rawColName, "=>", colName, "VAL", v?.extc_rst_cont01)
      // }
    });

    const sortedRowKeys = Array.from(rowMap.keys())
      .filter(k => !skipRowKeys.has(k))
      .sort((a, b) => Number(a) - Number(b));

    sortedRowKeys.forEach(rowKey => {
      const rowObj = rowMap.get(rowKey);
      arrayOfArray.push(buildRow(chartTitle, rowObj));
    });

    if (i === chartKeys.length - 1) arrayOfArray.push([]);
  }
}

function setExcelDataSingleChart(arrayOfArray, values, keyObj) {

  arrayOfArray.push([]);

  // 표데이터 출력
  let max_extc_rst_seq = 0;

  let group = values?.filter((value) => value?.extc_rst_seq > 0)
    .reduce((acc, value) => {
      if (acc[value?.img_extc_itnm]) acc[value?.img_extc_itnm].push(value);
      else acc[value?.img_extc_itnm] = [value];

      if (max_extc_rst_seq < value?.extc_rst_seq) max_extc_rst_seq = value?.extc_rst_seq;

      return acc;
    }, {});
  let chartTitle = keyObj["표타이틀"];
  chartTitle.unshift('');
  chartTitle.push("추출여부");

  arrayOfArray.push(chartTitle);


  for (let i = 0; i < Object.keys(group)?.length; i++) {
    let key = Object.keys(group)[i];
    let arr = group[Object.keys(group)[i]];

    let tmpArr = [];
    // array push 여부 판별 값
    let pushNum = 1;
    arr.forEach((value) => {

      if (value?.extc_rst_seq === 1) tmpArr.push(value?.img_extc_itnm);
      else {
        // [2025-04-11] 공백이면서 추출여부가 'N'인 값은 포함하지 않음
        if (value?.extc_rst_cont01 === '' && value?.extrtYn === 'N') pushNum++;
      }

      tmpArr.push(value?.extc_rst_cont01);

      if (value?.extc_rst_seq === max_extc_rst_seq) {
        tmpArr.push(value?.extrtYn);

        // [2025-04-11] 해당 항목 값 중 유효값이 있을 때만 push
        if (pushNum !== max_extc_rst_seq) arrayOfArray.push(tmpArr);

        tmpArr = [];
        pushNum = 1;
      }
    });
  }
}

// /**
//  * @name copyPreprocessingImageFileCategory
//  * @description 전처리 이미지 복사해서 분류파일에 저장
//  * @param {*} categoryList 
//  */
// async function copyPreprocessingImageFileCategory(originName, targetFileNm, requestId) {

//   const regex = /\.(jpg|jpeg|png|pdf|tif)$/i;
  
//   const originNamePath =  "/" + originName.replace(regex, ".png");
  
//   // 전처리 이미지를 특정 경로에 복사
//   const destDir = path.join(CATEGORY_IMAGE_DIR, requestId); // 카테고리_이미지 디렉토리
//   const destPath = path.join(destDir, originNamePath); // 저장될 경로

//   await clearDirectory(destDir);

//   // 전처리 이미지 경로
//   const prepcPath = path.join(OUTPUT_VOLUME, requestId, targetFileNm.replace("-001", ""), targetFileNm + "/preprocessing") + `/${targetFileNm}.png`;

//   try {
//     // 카테고리 디렉토리 없으면 생성
//     if (!fs.existsSync(destDir)) {
//       await fsPromises.mkdir(destDir, { recursive: true });
//     }
//     // 전처리 이미지 복사
//     await fsPromises.copyFile(prepcPath, destPath);

//     // Logger.log(`${prepcPath} → ${destPath} 복사 완료`);
//   } catch (err) {
//     console.error(`${prepcPath} 복사 실패:`, err.message);
//   }
// }

/**
 * extractionResultData 에서 arrtcd 가져오기 
 * @author Luna (syjang)
 * @param {Array} modelmap extractionResultData?.modelmapdata
 * @returns {Array} arrtcd return
 */
exports.getArrtcd = function getArrtcd(modelmap) {
  let contents = modelmap?.contents;
  let tcd = contents?.filter((v) => (v?.key === "cell"));
  let arrtcd = tcd[0]?.value || [];

  return arrtcd;
}

/**
 * extractionResultData 에서 arrmodel 가져오기 
 * @author Luna (syjang)
 * @param {Array} modelmap extractionResultData?.modelextract
 * @returns {Array} arrtcd return
 */
exports.getArrmodel = function getArrmodel(modelmap) {
  let contents = modelmap?.contents;
  let tcd = contents?.filter((v) => (v?.key === "modelextract"));
  let arrmodel = tcd[0]?.value || [];

  return arrmodel;
}

/**
 * arrtcd 중 name 이 keyword, mergetext 와 같은 그룹 리스트 가져오기
 * @author Luna (syjang)
 * @param {Array} arrtcd 기본 arrtcd ( modelmap?.contents 에서 key 가 cell 인 것들의 value )
 * @param {string} name 추출하고자 하는 항목과 동일한 group 에 있는 name
 * @returns {Array} arrtcd keyword, mergetext 에 name 이 포함되는 것의 groupidx 를 가져와 같은 그룹에 있는 항목들의 리스트를 return
 */
exports.getArrtcdValue = function getArrtcdValue(arrtcd, name) {
  let tcd = arrtcd?.filter((fv) => fv?.keyword === name || fv?.mergetext === name || fv?.keyword?.includes(name) || fv?.mergetext?.includes(name));
  let groupidx = tcd[0]?.groupidx || null;

  return arrtcd?.filter((fv) => fv?.groupidx === groupidx);
}

/**
 * arrtcd 중 index 기준으로 가져오기
 * @author Luna (syjang)
 * @param {Array} arrtcd 기본 arrtcd ( modelmap?.contents 에서 key 가 cell 인 것들의 value )
 * @param {string} index 추출하고자 하는 항목 index
 * @returns {Array} arrtcd keyword, mergetext 에 name 이 포함되는 것의 groupidx 를 가져와 같은 그룹에 있는 항목들의 리스트를 return
 */
exports.getArrtcdIdxValue = function getArrtcdIdxValue(arrtcd, index) {
  return arrtcd?.filter((fv) => fv?.index === index);
}

/**
 * arrtcd 를 활용하여 grouidx 가져오기
 * @author Luna (syjang)
 * @param {Array} arrtcd 기본 arrtcd ( modelmap?.contents 에서 key 가 cell 인 것들의 value )
 * @param {string} name 추출하고자 하는 항목과 동일한 group 에 있는 name
 * @returns {number} groupidx keyword, mergetext 에 name 이 포함되는 것의 groupidx를 return
 */
exports.getArrtcdGroupIdx = function getArrtcdGroupIdx(arrtcd, name) {
  let tcd = arrtcd?.filter((fv) => fv?.keyword === name || fv?.mergetext === name || fv?.keyword?.includes(name) || fv?.mergetext?.includes(name));
  let groupidx = tcd[0]?.groupidx || null;

  return groupidx;
}

/**
 * arrtcd 를 활용하여 grouidx 가져오기 - detectedIndex
 * @author Luna (syjang)
 * @param {Array} arrtcd 기본 arrtcd ( modelmap?.contents 에서 key 가 cell 인 것들의 value )
 * @param {string} detectedIndex 추출하고자 하는 항목과 동일한 group 에 있는 detectedIndex
 * @returns {number} groupidx keyword, mergetext 에 name 이 포함되는 것의 groupidx를 return
 */
exports.getArrtcdDetIdx = function getArrtcdDetIdx(arrtcd, detectedIndex) {
  let tcd = arrtcd?.filter((fv) => fv?.index === detectedIndex || fv?.index === detectedIndex);
  let groupidx = tcd[0]?.groupidx || null;

  return groupidx;
}

/**
 * arrtcd 중 groupidx 와 동일한 그룹 리스트 가져오기
 * @author Luna (syjang)
 * @param {Array} arrtcd 기본 arrtcd ( modelmap?.contents 에서 key 가 cell 인 것들의 value )
 * @param {number} groupidx 추출하고자 하는 groupidx
 * @returns {Array} arrtcd 넘겨받은 groupidx 와 같은 그룹에 있는 항목들의 리스트를 return
 */
exports.getArrtcdGroupValue = function getArrtcdGroupValue(arrtcd, groupidx) {
  return arrtcd?.filter((fv) => fv?.groupidx === groupidx);
}

/**
 * arrtcd 값에 있는 모든 mergetext 를 가져와서 string 형태로 return
 * @author Luna (syjang)
 * @param {Array} arrtcd 가공한 arrtcd ( 추출하고자 하는 grouidx 를 기준으로 getArrtcdValue 혹은 getArrtcdGroupValue 를 호출한 결과 )
 * @retruns {string} label 파라미터로 받은 arrtcd 의 모든 mergetext 값을 string 형태로 merge 하여 return 
 */
exports.setArrtcdLabel = function setArrtcdLabel(arrtcd) {
  let label = '';

  arrtcd?.forEach((tcd, idx) => {
    // if(idx !== 0) label += ' ';

    //mergetext 로 할시 등록된 대표어가 아닌 동의어들로도 키워드가 만들어지기 때문에 대표어로 바꿈 -20241025
    // label += tcd.mergetext;
    label += tcd.keyword;
  });

  return label;
}

/**
 * arrtcd 의 children, topitems, leftitems, rightitems, bottomitems return
 * @author Luna (syjang)
 * @param {Array} arrtcd 기본 arrtcd ( modelmap?.contents 에서 key 가 cell 인 것들의 value )
 * @param {string} name 기준이 되는 name
 * @param {number} index 기준이 되는 index (default = null)
 * @param {string} type children, top, left, right, bottom 중 입력
 * @returns {Array} arrtcd 의 children, topitems, leftitems, rightitems, bottomitems return
 */
exports.getArrtcdLowArr = function getArrtcdLowArr(arrtcd, name = null, index = null, type) {
  let tcd = arrtcd?.filter((fv) => fv?.keyword === name || fv?.mergetext === name || fv?.keyword?.includes(name) || fv?.mergetext?.includes(name));
  if (name !== null) tcd = arrtcd?.filter((fv) => fv?.keyword === name || fv?.mergetext === name || fv?.keyword?.includes(name) || fv?.mergetext?.includes(name));
  if (index !== null) tcd = arrtcd?.filter((fv) => fv?.index === index);

  switch (type) {
    case 'children':
      return tcd[0]?.children;
    case 'top':
      return tcd[0]?.relation?.topitems;
    case 'left':
      return tcd[0]?.relation?.leftitems;
    case 'right':
      return tcd[0]?.relation?.rightitems;
    case 'bottom':
      return tcd[0]?.relation?.bottomitems;
    default:
      return tcd;
  }

  return tcd;
}

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
  let result = '';

  let lastIdx = indexes[indexes.length - 1];
  while (true) {
    let tmpArrtcd = this.getArrtcdLowArr(arrtcd, name, lastIdx, direction);
    lastIdx = tmpArrtcd[0]?.index;

    if (typeof lastIdx === 'undefined') break;
    result += arrtcd[lastIdx]?.mergetext;
  }

  return result;
}

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
    if (typeof v?.ocrInfo !== 'undefined') {
      let coord = v?.ocrInfo[0]?.coordinates;
      let label = v?.ocrInfo[0]?.label;

      if (typeof coord !== 'undefined' && typeof label !== 'undefined' && label?.length > 0) widthSum += (coord[4] - coord[0] - 4) / label?.length * 0.8;
    }
  });
  widthAvg = widthSum / data?.values?.length;

  return widthAvg;
}

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
exports.getDistChkPoint = function getDistChkPoint(distChkPoint, widthAvg, arrtcd, label, index, direction = 'right') {
  let dist = 0;
  let tmpDistArr = this.getArrtcdLowArr(arrtcd, label, index, direction);

  if (tmpDistArr) dist = tmpDistArr[0]?.dist;
  if (dist > widthAvg + 4) distChkPoint = true;

  return distChkPoint;
}

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
exports.getNonCancelTxt = function getNonCancelTxt(arrtcd, groupValue = [], name, mainKey, subKey) {
  if (groupValue?.length < 1) {
    groupValue = this.getArrtcdValue(arrtcd, name);
    groupValue = groupValue?.filter((gv) => gv?.mergetext !== '');
  }

  let chkPoint = false;
  let result = [];

  for (let g = 0; g < groupValue?.length; g++) {
    if (groupValue[g]?.iskeyword === true && groupValue[g]?.keyword === mainKey) chkPoint = true;
    else if (groupValue[g]?.iskeyword === true && groupValue[g]?.keyword === subKey) chkPoint = false;
    else if (groupValue[g]?.mergetext?.includes(subKey)) chkPoint = false;

    if (!chkPoint || groupValue[g]?.iskeyword) continue;

    let childArr = groupValue[g]?.children?.filter((child) => !child?.cancelline);
    if (groupValue[g]?.iskeyword === false && childArr?.length > 0) {
      result.push(groupValue[g]?.mergetext);
      // Logger.log(`### ${groupValue[g]?.mergetext} -> `, groupValue[g]);
    }
  }

  return result;
}


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
}


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
}

const funcMinX = function (points) {
  let minX = Math.min.apply(null, points.map((v) => v[0]));
  return minX;
}
const funcMinY = function (points) {
  let minY = Math.min.apply(null, points.map((v) => v[1]));
  return minY;
}
const funcMaxX = function (points) {
  let maxX = Math.max.apply(null, points.map((v) => v[0]));
  return maxX;
}
const funcMaxY = function (points) {
  let maxY = Math.max.apply(null, points.map((v) => v[1]));
  return maxY;
}

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
}

exports.saveValuesCountToExcel = async function saveValuesCountToExcel(category, fileNm, valuesCount) {
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

    Logger.log(`📊 Values count saved: ${filePath}`);
  } catch (error) {
    Logger.error("⚠️ Error saving values count to Excel:", JSON.stringify({
      message: error.message,
      stack: error.stack.split("\n")
    }, null, 2));
  }
};


// ============================================= validation.js 추가 ===========================================================
function getAllextraDataWithPage(extractionResultData) {
  // Logger.log("############",extractionResultData)
  const out = [];

  //최상위 extraData (Page 정보 없음)
  if (Array.isArray(extractionResultData?.result)) {
    extractionResultData.result.forEach(v => {
      out.push({ ...v, __page: "ROOT" });
    });
  }

  //page1, page2, page3 ...
  if (extractionResultData && typeof extractionResultData === "object") {
    for (const [k, v] of Object.entries(extractionResultData)) {
      if (!/^Page\d+$/i.test(k)) continue;
      if (Array.isArray(v?.result)) {
        v.result.forEach(ed => {
          out.push({ ...ed, __page: k });
        })
      }
    }
  }
  // if (Array.isArray(extractionResultData?.extraData)) {
  //   extractionResultData.extraData.forEach(v => {
  //     out.push({ ...v, __page: "ROOT" });
  //   });
  // }

  // //page1, page2, page3 ...
  // if (extractionResultData && typeof extractionResultData === "object") {
  //   for (const [k, v] of Object.entries(extractionResultData)) {
  //     if (!/^Page\d+$/i.test(k)) continue;
  //     if (Array.isArray(v?.extraData)) {
  //       v.extraData.forEach(ed => {
  //         out.push({ ...ed, __page: k });
  //       })
  //     }
  //   }
  // }

  return out;
}

function toNumber(v) {
  return Number(String(v ?? "0").replace(/,/g, "")) || 0;
}

function isDate8(v) {
  return /^\d{8}$/.test(String(v ?? "").trim());
}

function validateExtraData(extraData) {
  const allRows = [["page", "group", "rowId", "item", "value", "result", "reason"]];
  const failRows = [["page", "group", "rowId", "item", "value", "result", "reason"]];

  const push = (page, group, rowId, item, value, ok, reason = "") => {
    const row = [page, group, rowId, item, String(value ?? ""), ok ? "OK" : "FAIL", reason];
    allRows.push(row)
    if (!ok) failRows.push(row)
  };

  //header 검증
  extraData
    .filter(v => v.extc_rst_cont10 === "header-contents")
    .forEach(v => {
      const page = v.__page;
      const item = v.img_extc_itnm;
      const value = v.extc_rst_cont01;
      const extrtYn = v.extrtYn;
      if (!value) {
        push(page, "HEADER", "-", item, value, false, "값 없음")
        return;
      }

      if (item?.includes("진료기간") && value && !isDate8(value)) {
        push(page, "HEADER", "-", item, value, false, "날짜 형식 오류 (YYYYMMDD");
        return;
      }

      push(page, "HEADER", "-", item, value, true);
    });
  // TABLE ROW 구성
  const tableItems = extraData.filter(v => v.chartNm === "표데이터");
  const rows = {};

  tableItems.forEach(v => {
    const key = `${v.__page}_${v.extc_itm_no}`;
    if (!rows[key]) rows[key] = { page: v.__page, rowId: v.extc_itm_no, cols: {} };
    rows[key].cols[v.extrt_raw_itm_nm || v.img_extc_itnm] = v.extc_rst_cont01;
  });

  //table 검증
  Object.values(rows).forEach(r => {
    const { page, rowId, cols } = r;

    // Logger.log(cols["본인부담"]);
    // Logger.log(cols["공단부담"]);
    // Logger.log(cols["전액본인부담"]);
    //금액검증
    if (cols["금액"]) {
      const 금액 = toNumber(cols["금액"]);
      const 횟수 = toNumber(cols["횟수"] ?? 1);
      const 일수 = toNumber(cols["일수"] ?? 1);
      const 총액 = toNumber(cols["총액"]);
      
      const ok = 금액 * 횟수 * 일수 === 총액;
      // Logger.log(`${금액}=금액, ${횟수}=횟수, ${일수}=일수, ${금액 * 횟수 * 일수} === ${총액}(총액)`)
      // Logger.log(cols['횟수'],">>>>>>>>>>>" ,횟수)
      // Logger.log(cols['일수'],">>>>>>>>>>>" ,일수)
      push(
        page, "표데이터_금액", rowId,
        "금액검증(금액x횟수x일수)",
        `금액=${cols["금액"]}, 횟수=${횟수},일수=${일수},총액=${cols["총액"]}`,
        ok,
        ok ? "" : `계산불일지`
      );
    }

    if (cols["합계"]) {
      const 급여총액 = toNumber(cols["합계"]);
      const 본인부담 = toNumber(cols["급여_본인부담총액"]);
      const 공단부담 = toNumber(cols["급여_공단부담총액"]);
      const 전액본인부담 = toNumber(cols["급여_전액본인부담총액"]);
      const 비급여 = toNumber(cols["비급여총액"]);

      const ok2 = 본인부담 + 공단부담 + 전액본인부담 + 비급여 === 급여총액;

      push(
        page, "표데이터_진료비총액", rowId,
        "합계 검증(본인부담+공단부담+전액본인부담+비급여)",
        `본인부담=${cols["급여_본인부담총액"]}, 공단부담=${cols["급여_공단부담총액"]}, 전액본인부담=${cols["급여_전액본인부담총액"]} 비급여=${cols["비급여총액"]} 합계=${cols["합계"]}`,
        ok2,
        ok2 ? "" : `계산불일치`
      )
    }
    // };


    // 부담금 합계 검증
    // const 본인 = toNumber(cols["본인부담"]);
    // const 공단 = toNumber(cols["공단부담"]);
    // const 전액 = toNumber(cols["전액본인부담"]);
    // const 비급여 = toNumber(cols["비급여"]);
    // const 총액 = toNumber(cols["총액"]);

    // if (총액 > 0) {
    //   const sum = 본인 + 공단 + 전액 + 비급여;
    //   const ok = sum === 총액;

    //   push(
    //     page,"TABLE",rowId,
    //     "부담금합계검증",
    //     `본인=${본인},공단=${공단},전액=${전액},비급여=${비급여},총액=${총액}`
    //   )
    // }
  });

  return { allRows, failRows }
}