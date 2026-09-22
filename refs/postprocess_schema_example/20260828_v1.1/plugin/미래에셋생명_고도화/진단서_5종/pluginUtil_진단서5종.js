// const {Logger}              = require('common/logger');
const { Logger } = require("/usr/src/app/dist/apps/extn/libs/common/src/logger");

const path                = require('path');
const fs                  = require('fs');
const fsPromises          = require('fs/promises');

const xlsx                = require("xlsx");
const excelPath           = path.join("/data/data/excel");
const valuePath           = path.join("/data/data/value");

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
      for(let i=0; i<Object.keys(dataObj)?.length; i++) {
        let key = Object.keys(dataObj)[i];

        if(filterTxt !== null) dataObj[key] = dataObj[key]?.filter((o) => o?.userdescription === filterTxt);
        if(stType !== null) dataObj[key] = dataObj[key]?.filter((o) => o?.st_type === stType);
        if(resultTxt !== null) dataObj[key] = dataObj[key]?.filter((o) => o?.value?.result === resultTxt);
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
  Logger.log('\n=========================================================================================================================================================');
  values?.sort((a, b) => {
    if (a.lvl_no != b.lvl_no) return a.lvl_no - b.lvl_no;
    else return a.extc_rst_seq - b.extc_rst_seq;
  });

  if(!type.includes('simple')) Logger.log('INDEX\t\t추출ID\t\t추출레벨번호\t추출일련번호\t본인신뢰도값\t사고발생일자\t차트이름\t추출항목명\t\t추출내용');
  else Logger.log('INDEX\t\t추출여부\t차트이름\t\t\t추출항목명\t\t\t추출내용');

  values?.forEach((value, i) => {
    let tab = '';
    if (this.getBytes(value.img_extc_itnm) < 7) tab = '\t\t\t\t';
    else if (this.getBytes(value.img_extc_itnm) < 16) tab = '\t\t\t';
    else tab = '\t';

    if((type.includes('short') && value.extc_rst_seq < 1) || !type.includes('short')) {
      if(!type.includes('simple')) 
        Logger.log((i+1) + '\t\t' + value.extc_itm_no + '\t\t' 
        + value.lvl_no + '\t\t' + value.extc_rst_seq + '\t\t'
         + value.self_rlbtr_vl + '\t\t' + value.acd_ogtdt+ '\t\t' + value.extc_rst_cont10 +'\t\t'+ value.img_extc_itnm 
        + '\t\t' + value.extc_rst_cont01) ;
      else Logger.log(i + '\t\t' + value.extrtYn + '\t\t' + value.chartNm 
        + (value.chartNm === null ? '\t\t\t\t' : '\t\t') + value.extrtItmNm + tab + value.extrtCntnt);
    }
  });
  
  Logger.log('=========================================================================================================================================================\n');
}
// exports.printResultLog = function printResultLog(type, values) {
//   Logger.log('\n=========================================================================================================================================================');
//   values?.sort((a, b) => {
//     if (a.extrtLvlNo != b.extrtLvlNo) return a.extrtLvlNo - b.extrtLvlNo;
//     else return a.extrtSno - b.extrtSno;
//   });

//   if(!type.includes('simple')) Logger.log('INDEX\t\t추출ID\t\t추출레벨번호\t추출일련번호\t추출여부\t본인신뢰도값\t추출항목명\t\t\t추출내용\t\t\t차트이름');
//   else Logger.log('INDEX\t\t추출여부\t차트이름\t\t\t추출항목명\t\t\t추출내용');

//   values?.forEach((value, i) => {
//     let tab = '';
//     if (this.getBytes(value.extrtItmNm) < 7) tab = '\t\t\t\t';
//     else if (this.getBytes(value.extrtItmNm) < 16) tab = '\t\t\t';
//     else tab = '\t';

//     if((type.includes('short') && value.extrtSno < 1) || !type.includes('short')) {
//       if(!type.includes('simple')) Logger.log((i+1) + '\t\t' + value.extrtId + '\t\t' + value.extrtLvlNo + '\t\t' + value.extrtSno + '\t\t' + value.extrtYn + '\t\t' + value.selfRlbtyVal + '\t\t' + value.extrtItmNm + tab + value.extrtCntnt + '\t\t\t' + value.chartNm);
//       else Logger.log(i + '\t\t' + value.extrtYn + '\t\t' + value.chartNm + (value.chartNm === null ? '\t\t\t\t' : '\t\t') + value.extrtItmNm + tab + value.extrtCntnt);
//     }
//   });
  
//   Logger.log('=========================================================================================================================================================\n');
// }

/**
 * 결과 로그 출력 엑셀 변환 용
 * @author Luna (syjang)
 * @param {string} type 
 * @param {object} values 
 */
exports.printResultLogExcel = function printResultLogExcel(type, values, extractionResultData, keyObj) {

  // [2025-04-10] 추출여부 'Y'인 항목만 남기기
  // values = values?.filter((value) => value?.extrtYn === 'Y');

  Logger.log('\n=========================================excel 추출================================================================================================================');

  if(type.includes("log")) {
    values?.sort((a, b) => {
      if (a.lvl_no != b.lvl_no) return a.lvl_no - b.lvl_no;
      else return a.extc_rst_seq - b.extc_rst_seq;
    });

    Logger.log('INDEX|추출ID|추출레벨번호|추출일련번호|추출여부|본인신뢰도값|추출항목명|추출내용');
    values?.forEach((value, i) => {
      if((type.includes('short') && value.extc_rst_seq < 1) || !type.includes('short')) {
        Logger.log((i+1) + '|' + value.extc_itm_no + '|' + value.lvl_no + '|' + value.extc_rst_seq + '|' + value.extrtYn + '|' + value.self_rlbtr_vl + '|' + value.img_extc_itnm + '|' + value.extc_rst_cont01);
      }
    });
  }

  // 엑셀 데이터 셋팅
  if(type.includes("excel")) {

    let arrayOfArray = [["레벨번호","추출항목명","추출내용", "추출여부"]];
    // let arrayOfArray = [["레벨번호","추출항목명","추출내용"]];
  
    // 표데이터가 아닌 값 먼저 출력
    values?.filter((value) => (value?.extc_rst_seq < 1)&&(value?.chartNm!="계"))
      .forEach((value) => {
        // [2025-04-13] 공백이면서 추출여부가 'N'인 값은 포함하지 않음
        if(!(value?.extc_rst_cont01?.length==0 && value?.extrtYn=="N")) {
          arrayOfArray.push([value?.lvl_no, value?.img_extc_itnm, value?.extc_rst_cont01, value?.extrtYn]);
        }
        // arrayOfArray.push([value?.lvl_no, value?.img_extc_itnm, value?.extc_rst_cont01, value?.extrtYn]);
      });

    let salaryItems = []; // "일부본인부담금"을 구분하기 위한 카운터
    let seen = new Set();
    values?.filter((value)=>(value?.extc_rst_seq < 1)&&(value?.chartNm=="계"))
      .forEach((value)=>{
        let newExtractionItem = `${value?.chartNm}_${value?.img_extc_itnm}`;

        // "일부본인부담금"이면 따로 저장 후 나중에 처리
        if (value?.img_extc_itnm === "일부본인부담금") {
          salaryItems.push({ lvlNo:value?.lvl_no, name: newExtractionItem, content: value?.extc_rst_cont01, result: value?.extrtYn, chart: value?.chartNm });
          // salaryItems.push({ lvlNo:value?.lvl_no, name: newExtractionItem, content: value?.extc_rst_cont01, chart: value?.chartNm });
        } else {
          let uniqueKey = `${value?.lvl_no}|${newExtractionItem}|${value?.extc_rst_cont01}|${value?.extrtYn}`;
          // let uniqueKey = `${value?.lvl_no}|${newExtractionItem}|${value?.extc_rst_cont01}`;
          if (!seen.has(uniqueKey)) {
            seen.add(uniqueKey);
            arrayOfArray.push([value?.lvl_no,newExtractionItem, value?.extc_rst_cont01, value?.extrtYn]);
            // arrayOfArray.push([value?.lvl_no,newExtractionItem, value?.extc_rst_cont01]);
          }
        }
      });

    salaryItems.forEach((item, index) => {
      let newName = index % 2 === 0 ? `${item.chart}_일부본인부담금_급여` : `${item.chart}_일부본인부담금_비급여`;
      let uniqueKey = `${newName}|${item.content}|${item.result}`;
      if (!seen.has(uniqueKey)) {
        seen.add(uniqueKey);
        arrayOfArray.push([item.lvlNo, newName, item.content, item.result]);
      }
    });
    values.forEach((v)=>{
     // Logger.log(v.img_extc_itnm,"===>",v.extc_rst_seq,"=====>",v.chartNm)

    })

    let sortedArray = [arrayOfArray[0], ...arrayOfArray.slice(1).sort((a, b) => a[0] - b[0])];

    if(keyObj['표추출항목'] && keyObj['표추출항목']?.length > 0) {
      // 진료비영수증
      setExcelDataSingleChart(sortedArray, values, keyObj);
    } else {
      // 표가 여러 개인 경우
      setExcelDataDozenChart(sortedArray, values, keyObj);
    }

    // [2025-04-10] 레벨번호, 추출여부 제거
    sortedArray?.forEach((sa) => {
      if(sa?.length > 0) {
        if(typeof(sa[0]) === "number") sa.shift();
        else if(sa[0]?.includes("레벨번호") || sa[0]?.includes("표데이터")) sa.shift();
        sa.pop();
      }
    });

    // 엑셀 생성
    let fileNm = extractionResultData.modelmapdata.fileNm;
    let category = extractionResultData.modelmapdata.category;
  
    let splitBook = xlsx.utils.book_new();
    let excelfileName = fileNm + ".xlsx";

    
    let document = xlsx.utils.aoa_to_sheet(sortedArray);
    
    document["!cols"]     = [{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100}];

    xlsx.utils.book_append_sheet(splitBook, document, "결과");
  
    if (!fs.existsSync(excelPath)) fsPromises.mkdir(excelPath);
    if (!fs.existsSync(path.join(excelPath, category))) fsPromises.mkdir(path.join(excelPath, category));
  
    xlsx.writeFile(splitBook, path.join(excelPath, category, excelfileName));
  }

  Logger.log('=========================================================================================================================================================\n');
}

exports.diagExcel = function diagExcel(type, values, extractionResultData, keyObj){
  if(type.includes("excel")){
    const arrayOfArray=[
      ["img_extc_itnm", "extc_rst_cont01","extc_rst_cont09","extc_rst_cont10"]
    ];

    values?.forEach((value)=>{
      arrayOfArray.push([
        value?.img_extc_itnm ||"",
        value?.extc_rst_cont01 ||"",
        value?.extc_rst_cont09 ||"",
        value?.extc_rst_cont10 ||""
      ]);
    });
    let fileNm = extractionResultData.modelmapdata.fileNm;
    let category = extractionResultData.modelmapdata.category;

    let splitBook = xlsx.utils.book_new();
    let excelfileName = fileNm + ".xlsx";

    let document = xlsx.utils.aoa_to_sheet(arrayOfArray);
    Object.keys(document).forEach((cell)=>{
      if(cell[0]=== "!") return;
      document[cell].t ="s";
      document[cell].v = document[cell].v ==null ? "":String(document[cell].v);
      document[cell].z="@"
    })
    document["!cols"]     = [{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100}];

    xlsx.utils.book_append_sheet(splitBook, document, "결과");
  
    if (!fs.existsSync(excelPath)) fsPromises.mkdir(excelPath);
    if (!fs.existsSync(path.join(excelPath, category))) fsPromises.mkdir(path.join(excelPath, category));
  
    xlsx.writeFile(splitBook, path.join(excelPath, category, excelfileName));
  }
}
// exports.printResultLogExcel = function printResultLogExcel(type, values, extractionResultData, keyObj) {

//   // [2025-04-10] 추출여부 'Y'인 항목만 남기기
//   // values = values?.filter((value) => value?.extrtYn === 'Y');

//   Logger.log('\n=========================================excel 추출================================================================================================================');

//   if(type.includes("log")) {
//     values?.sort((a, b) => {
//       if (a.extrtLvlNo != b.extrtLvlNo) return a.extrtLvlNo - b.extrtLvlNo;
//       else return a.extrtSno - b.extrtSno;
//     });

//     Logger.log('INDEX|추출ID|추출레벨번호|추출일련번호|추출여부|본인신뢰도값|추출항목명|추출내용');
//     values?.forEach((value, i) => {
//       if((type.includes('short') && value.extrtSno < 1) || !type.includes('short')) {
//         Logger.log((i+1) + '|' + value.extrtId + '|' + value.extrtLvlNo + '|' + value.extrtSno + '|' + value.extrtYn + '|' + value.selfRlbtyVal + '|' + value.extrtItmNm + '|' + value.extrtCntnt);
//       }
//     });
//   }

//   // 엑셀 데이터 셋팅
//   if(type.includes("excel")) {

//     let arrayOfArray = [["레벨번호","추출항목명","추출내용", "추출여부"]];
//     // let arrayOfArray = [["레벨번호","추출항목명","추출내용"]];
  
//     // 표데이터가 아닌 값 먼저 출력
//     values?.filter((value) => (value?.extrtSno < 1)&&(value?.chartNm!="계"))
//       .forEach((value) => {
//         // [2025-04-13] 공백이면서 추출여부가 'N'인 값은 포함하지 않음
//         if(!(value?.extrtCntnt?.length==0 && value?.extrtYn=="N")) {
//           arrayOfArray.push([value?.extrtLvlNo, value?.extrtItmNm, value?.extrtCntnt, value?.extrtYn]);
//         }
//         // arrayOfArray.push([value?.extrtLvlNo, value?.extrtItmNm, value?.extrtCntnt, value?.extrtYn]);
//       });

//     let salaryItems = []; // "일부본인부담금"을 구분하기 위한 카운터
//     let seen = new Set();
//     values?.filter((value)=>(value?.extrtSno < 1)&&(value?.chartNm=="계"))
//       .forEach((value)=>{
//         let newExtractionItem = `${value?.chartNm}_${value?.extrtItmNm}`;

//         // "일부본인부담금"이면 따로 저장 후 나중에 처리
//         if (value?.extrtItmNm === "일부본인부담금") {
//           salaryItems.push({ lvlNo:value?.extrtLvlNo, name: newExtractionItem, content: value?.extrtCntnt, result: value?.extrtYn, chart: value?.chartNm });
//           // salaryItems.push({ lvlNo:value?.extrtLvlNo, name: newExtractionItem, content: value?.extrtCntnt, chart: value?.chartNm });
//         } else {
//           let uniqueKey = `${value?.extrtLvlNo}|${newExtractionItem}|${value?.extrtCntnt}|${value?.extrtYn}`;
//           // let uniqueKey = `${value?.extrtLvlNo}|${newExtractionItem}|${value?.extrtCntnt}`;
//           if (!seen.has(uniqueKey)) {
//             seen.add(uniqueKey);
//             arrayOfArray.push([value?.extrtLvlNo,newExtractionItem, value?.extrtCntnt, value?.extrtYn]);
//             // arrayOfArray.push([value?.extrtLvlNo,newExtractionItem, value?.extrtCntnt]);
//           }
//         }
//       });

//     salaryItems.forEach((item, index) => {
//       let newName = index % 2 === 0 ? `${item.chart}_일부본인부담금_급여` : `${item.chart}_일부본인부담금_비급여`;
//       let uniqueKey = `${newName}|${item.content}|${item.result}`;
//       if (!seen.has(uniqueKey)) {
//         seen.add(uniqueKey);
//         arrayOfArray.push([item.lvlNo, newName, item.content, item.result]);
//       }
//     });
//     values.forEach((v)=>{
//      // Logger.log(v.extrtItmNm,"===>",v.extrtSno,"=====>",v.chartNm)

//     })

//     let sortedArray = [arrayOfArray[0], ...arrayOfArray.slice(1).sort((a, b) => a[0] - b[0])];

//     if(keyObj['표추출항목'] && keyObj['표추출항목']?.length > 0) {
//       // 진료비영수증
//       setExcelDataSingleChart(sortedArray, values, keyObj);
//     } else {
//       // 표가 여러 개인 경우
//       setExcelDataDozenChart(sortedArray, values, keyObj);
//     }

//     // [2025-04-10] 레벨번호, 추출여부 제거
//     sortedArray?.forEach((sa) => {
//       if(sa?.length > 0) {
//         if(typeof(sa[0]) === "number") sa.shift();
//         else if(sa[0]?.includes("레벨번호") || sa[0]?.includes("표데이터")) sa.shift();
//         sa.pop();
//       }
//     });

//     // 엑셀 생성
//     let fileNm = extractionResultData.modelmapdata.fileNm;
//     let category = extractionResultData.modelmapdata.category;
  
//     let splitBook = xlsx.utils.book_new();
//     let excelfileName = fileNm + ".xlsx";

    
//     let document = xlsx.utils.aoa_to_sheet(sortedArray);
    
//     document["!cols"]     = [{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100},{wpx:100}];

//     xlsx.utils.book_append_sheet(splitBook, document, "결과");
  
//     if (!fs.existsSync(excelPath)) fsPromises.mkdir(excelPath);
//     if (!fs.existsSync(path.join(excelPath, category))) fsPromises.mkdir(path.join(excelPath, category));
  
//     xlsx.writeFile(splitBook, path.join(excelPath, category, excelfileName));
//   }

//   Logger.log('=========================================================================================================================================================\n');
// }

function setExcelDataDozenChart(arrayOfArray, values, keyObj) {
  // 표데이터 출력
  let max_extrtSno = 0;

  let group = values?.filter((value) => value?.extrtSno > 0)
    .reduce((acc, value) => {
      if(acc[value?.chartNm]) acc[value?.chartNm].push(value);
      else acc[value?.chartNm] = [value];

      if(max_extrtSno < value?.extrtSno) max_extrtSno = value?.extrtSno;

      return acc;
    }, {});
    
  for(let i=0; i<Object.keys(group)?.length; i++) {

    arrayOfArray.push([]);
    
    let key = Object.keys(group)[i];
    let arr = group[Object.keys(group)[i]];

    
    let chartTitle = keyObj["표타이틀"];
    if(chartTitle.length < 1 && keyObj[`표타이틀_`+key]?.length > 0) {
      chartTitle = keyObj[`표타이틀_`+key];

      chartTitle = chartTitle.filter((title) => {
        let result = false;
        for(let i=0; i<arr.length-1; i++) {
          if(arr[i]?.extrtItmNm === title) {
            result = true; break;
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
    let lvlNum = 0;
    let init = "Y";
    let extrtArr = [];
    let extrtNum = [];

    arr.forEach((value, idx) => {
      // 진료비영수증의 경우 진찰료, 입원료 등 기입
      if(chartTitle.indexOf(value?.extrtItmNm) < 0) {
        
        if(value?.extrtSno === 1) tmpArr.push(value?.extrtItmNm);

        tmpArr.push(value?.extrtCntnt);

        if(value?.extrtSno === max_extrtSno) {
          tmpArr.push(value?.extrtYn);

          arrayOfArray.push(tmpArr);

          tmpArr = [];
        }
      } else {

        // 진료비세부내역서와 같은 유형의 표 데이터는 레벨번호 기입
        if(value?.extrtSno === 1) {
          tmpArr.push(value?.extrtLvlNo);

          // [2025-04-11] 유효값 여부 확인용
          if(lvlNum !== 0) init = "N";
          lvlNum = value?.extrtLvlNo;
        }

        // [2025-04-11] 유효값 여부 확인용
        if(lvlNum === value?.extrtLvlNo) {
          // [2025-04-11] 첫 line일 경우 extrtNum push 필요
          if(init === "Y") {
            // [2025-04-11] 유효값이 아닐 경우는 1 push
            if(value?.extrtCntnt?.length===0 && value?.extrtYn==="N") {
              extrtNum.push(1);
            // [2025-04-11] 유효값일 경우에는 0 push
            } else {
              extrtNum.push(0);
            }
          
          // 두번째 line 부터는 해당 순서에 반영
          } else {
            // [2025-04-11] 유효값이 아닐 경우는 1 더하기
            if(value?.extrtCntnt?.length===0 && value?.extrtYn==="N") {
              extrtNum[value?.extrtSno-1] = extrtNum[value?.extrtSno-1] + 1;
            } 
          }
        }

        tmpArr.push(value?.extrtCntnt);
        if(value?.extrtSno === chartTitle.length-2) {
          tmpArr.push(value?.extrtYn);

          // arrayOfArray.push(tmpArr);
          // [2025-04-11] 유효값 반영
          extrtArr.push(tmpArr);

          tmpArr = [];
        // [2024.10.28.]진료비세부내역서 push  
        } else if(value?.extrtSno === max_extrtSno) {
          tmpArr.push(value?.extrtYn);
  
          // arrayOfArray.push(tmpArr);
          // [2025-04-11] 유효값 반영
          extrtArr.push(tmpArr);

          tmpArr = [];
        }
      }
    });

    // [2025-04-11] 레벨번호, 추출여부 반영
    extrtNum.unshift(0);
    extrtNum.push(0);

    let deleteNum = [];
    if(extrtNum?.length>2 && extrtArr?.length>0) {
      // 유효값이 아닌 row 추출
      extrtNum?.forEach((extrt, i) => {
        if(extrt === extrtArr?.length) deleteNum.push(i);
      });
      
    }

    // '표타이틀'에서 유효값만 남기기
    let filteredTitle = chartTitle.filter((_, idx) => !deleteNum.includes(idx));
    // extrtArr에서 유효값만 남기기
    let cleanedArr = extrtArr.map(row =>
      row.filter((_, idx) => !deleteNum.includes(idx))
    );

    if(filteredTitle?.length>0 && cleanedArr?.length>0) {
      // 기존 '표타이틀' 제거
      arrayOfArray.pop();

      arrayOfArray.push(filteredTitle);
      arrayOfArray.push(...cleanedArr);
    }

    if(i === Object.keys(group)?.length-1) arrayOfArray.push([]);
  }

}

function setExcelDataSingleChart(arrayOfArray, values, keyObj) {
  
  arrayOfArray.push([]);

  // 표데이터 출력
  let max_extrtSno = 0;

  let group = values?.filter((value) => value?.extrtSno > 0)
    .reduce((acc, value) => {
      if(acc[value?.extrtItmNm]) acc[value?.extrtItmNm].push(value);
      else acc[value?.extrtItmNm] = [value];

      if(max_extrtSno < value?.extrtSno) max_extrtSno = value?.extrtSno;

      return acc;
    }, {});
  let chartTitle = keyObj["표타이틀"];
  chartTitle.unshift('');
  chartTitle.push("추출여부");

  arrayOfArray.push(chartTitle);
  
  
  for(let i=0; i<Object.keys(group)?.length; i++) {
    let key = Object.keys(group)[i];
    let arr = group[Object.keys(group)[i]];

    let tmpArr = [];
    // array push 여부 판별 값
    let pushNum = 1;
    arr.forEach((value) => {

      if(value?.extrtSno === 1) tmpArr.push(value?.extrtItmNm);
      else {
        // [2025-04-11] 공백이면서 추출여부가 'N'인 값은 포함하지 않음
        if(value?.extrtCntnt==='' && value?.extrtYn ==='N') pushNum++;
      }

      tmpArr.push(value?.extrtCntnt);

      if(value?.extrtSno === max_extrtSno) {
        tmpArr.push(value?.extrtYn);

        // [2025-04-11] 해당 항목 값 중 유효값이 있을 때만 push
        if(pushNum!==max_extrtSno) arrayOfArray.push(tmpArr);

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
  let contents  = modelmap?.contents;
  let tcd       = contents?.filter((v) => (v?.key === "cell"));
  let arrtcd    = tcd[0]?.value || [];

  return arrtcd;
}

/**
 * extractionResultData 에서 arrmodel 가져오기 
 * @author Luna (syjang)
 * @param {Array} modelmap extractionResultData?.modelextract
 * @returns {Array} arrtcd return
 */
exports.getArrmodel = function getArrmodel(modelmap) {
  let contents    = modelmap?.contents;
  let tcd         = contents?.filter((v) => (v?.key === "modelextract"));
  let arrmodel    = tcd[0]?.value || [];

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
  let tcd       = arrtcd?.filter((fv)=>fv?.keyword === name || fv?.mergetext === name || fv?.keyword?.includes(name) || fv?.mergetext?.includes(name));
  let groupidx  = tcd[0]?.groupidx || null;

  return arrtcd?.filter((fv)=>fv?.groupidx === groupidx);
}

/**
 * arrtcd 중 index 기준으로 가져오기
 * @author Luna (syjang)
 * @param {Array} arrtcd 기본 arrtcd ( modelmap?.contents 에서 key 가 cell 인 것들의 value )
 * @param {string} index 추출하고자 하는 항목 index
 * @returns {Array} arrtcd keyword, mergetext 에 name 이 포함되는 것의 groupidx 를 가져와 같은 그룹에 있는 항목들의 리스트를 return
 */
exports.getArrtcdIdxValue = function getArrtcdIdxValue(arrtcd, index) {
  return arrtcd?.filter((fv)=>fv?.index === index);
}

/**
 * arrtcd 를 활용하여 grouidx 가져오기
 * @author Luna (syjang)
 * @param {Array} arrtcd 기본 arrtcd ( modelmap?.contents 에서 key 가 cell 인 것들의 value )
 * @param {string} name 추출하고자 하는 항목과 동일한 group 에 있는 name
 * @returns {number} groupidx keyword, mergetext 에 name 이 포함되는 것의 groupidx를 return
 */
exports.getArrtcdGroupIdx = function getArrtcdGroupIdx(arrtcd, name) {
  let tcd       = arrtcd?.filter((fv)=>fv?.keyword === name || fv?.mergetext === name || fv?.keyword?.includes(name) || fv?.mergetext?.includes(name));
  let groupidx  = tcd[0]?.groupidx || null;

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
  let tcd       = arrtcd?.filter((fv)=>fv?.index === detectedIndex || fv?.index === detectedIndex);
  let groupidx  = tcd[0]?.groupidx || null;

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
  return arrtcd?.filter((fv)=>fv?.groupidx === groupidx);
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
exports.getArrtcdLowArr = function getArrtcdLowArr(arrtcd, name=null, index=null, type) {
  let tcd = arrtcd?.filter((fv)=>fv?.keyword === name || fv?.mergetext === name || fv?.keyword?.includes(name) || fv?.mergetext?.includes(name));
  if(name !== null)   tcd = arrtcd?.filter((fv) => fv?.keyword === name || fv?.mergetext === name || fv?.keyword?.includes(name) || fv?.mergetext?.includes(name));
  if(index !== null)  tcd = arrtcd?.filter((fv) => fv?.index === index);

  switch(type) {
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
    default : 
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
  while (true){
    let tmpArrtcd = this.getArrtcdLowArr(arrtcd, name, lastIdx, direction);
    lastIdx = tmpArrtcd[0]?.index;

    if(typeof lastIdx === 'undefined') break;
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
  let dist     = 0;

  // Page1.values[0].data[0].values.length > 1 인 경우 cell 간 width의 평균 측정
  let widthSum  = 0;
  data?.values?.forEach((v) => {
    if(typeof v?.ocrInfo !== 'undefined') {
      let coord   = v?.ocrInfo[0]?.coordinates;
      let label   = v?.ocrInfo[0]?.label;
  
      if(typeof coord !== 'undefined' && typeof label !== 'undefined' && label?.length > 0) widthSum += (coord[4]-coord[0]-4)/label?.length*0.8;
    }
  });
  widthAvg = widthSum/data?.values?.length;

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
exports.getDistChkPoint = function getDistChkPoint(distChkPoint, widthAvg, arrtcd, label, index, direction='right') {
  let dist        = 0;
  let tmpDistArr  = this.getArrtcdLowArr(arrtcd, label, index, direction);

  if(tmpDistArr) dist = tmpDistArr[0]?.dist;
  if(dist > widthAvg + 4) distChkPoint = true;

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
exports.getNonCancelTxt = function getNonCancelTxt(arrtcd, groupValue=[], name, mainKey, subKey) {
  if(groupValue?.length < 1) {
    groupValue  = this.getArrtcdValue(arrtcd, name);
    groupValue  = groupValue?.filter((gv) => gv?.mergetext !== '');
  }
  
  let chkPoint  = false;
  let result    = [];

  for (let g = 0; g < groupValue?.length; g++) {
    if(groupValue[g]?.iskeyword === true && groupValue[g]?.keyword === mainKey) chkPoint = true;
    else if(groupValue[g]?.iskeyword === true && groupValue[g]?.keyword === subKey) chkPoint = false;
    else if(groupValue[g]?.mergetext?.includes(subKey)) chkPoint = false;

    if (!chkPoint || groupValue[g]?.iskeyword) continue;

    let childArr = groupValue[g]?.children?.filter((child)=>!child?.cancelline);
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

const funcMinX = function(points){
    let minX = Math.min.apply(null, points.map((v) => v[0]));
    return minX;
}
const funcMinY = function(points){
    let minY = Math.min.apply(null, points.map((v) => v[1]));
    return minY;
}
const funcMaxX = function(points){
    let maxX = Math.max.apply(null, points.map((v) => v[0]));
    return maxX;
}
const funcMaxY = function(points){
    let maxY = Math.max.apply(null, points.map((v) => v[1]));
    return maxY;
}

exports.getBytes = function getBytes(contents) {
  let str;
  let cnt = 0;
  let len = contents?.length;

  for(let i=0; i<len; i++) {
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
    Logger.error("⚠️ Error saving values count to Excel:", error);
  }
};